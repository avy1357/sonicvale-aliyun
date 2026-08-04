import re
import difflib
import logging
from typing import List, Dict, Tuple, Optional


class TextCorrectorFinal:
    # 默认配置参数
    DEFAULT_BASE_THRESHOLD = 0.65  # 基础相似度阈值
    DEFAULT_BASE_WINDOW = 30  # 基础搜索窗口
    DEFAULT_EXTENDED_WINDOW = 80  # 扩展搜索窗口（匹配失败时使用）

    def __init__(self, base_threshold: Optional[float] = None, base_window: int = None):
        """初始化文本校正器

        Args:
            base_threshold: 基础相似度阈值，默认0.65
            base_window: 基础搜索窗口大小，默认30
        """
        self.base_threshold = base_threshold if base_threshold is not None else self.DEFAULT_BASE_THRESHOLD
        self.base_window = base_window or self.DEFAULT_BASE_WINDOW
        self.extended_window = self.DEFAULT_EXTENDED_WINDOW

    def clean_text(self, text: str) -> str:
        """清理文本用于最终输出，移除换行符和全角空格，保留引号。"""
        text = re.sub(r'[\n\r\u3000]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def clean_for_compare(self, text: str) -> str:
        """清理文本用于相似度比较，移除换行符、全角空格和引号。"""
        text = re.sub(r'[\n\r\u3000]', '', text)
        text = re.sub(r'["""「」『』]', '', text)  # 仅在比较时移除引号
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def get_adaptive_threshold(self, sentence: str) -> float:
        """根据句子长度自适应调整相似度阈值。
        
        短句子容易误匹配，需要更高阈值；长句子可以适当降低阈值。
        """
        length = len(self.clean_for_compare(sentence))
        
        if length <= 5:
            # 非常短的句子，需要很高的阈值防止误匹配
            return max(self.base_threshold, 0.85)
        elif length <= 10:
            # 短句子
            return max(self.base_threshold, 0.75)
        elif length <= 20:
            # 中等长度
            return self.base_threshold
        else:
            # 长句子可以适当降低阈值
            return max(self.base_threshold - 0.05, 0.55)

    def _looks_like_abbreviation(self, sentence_with_dot: str) -> bool:
        """
        判断当前这一个 '.' 更像是缩写的一部分，而不是句子结束。
        sentence_with_dot: 当前已经累积的句子（包含这个点）
        """
        s = sentence_with_dot.rstrip()
        # 找到以 . 结尾的最后一个 token（字母/数字/点）
        m = re.search(r'([A-Za-z0-9\.]+)\.$', s)
        if not m:
            return False

        token = m.group(1)  # 不包含最后这个点，但可能包含内部的 .

        # 1) 小写长度很短的缩写，例如 Mr. Dr. etc.
        #    这里简单认为：1~4 个字母，首字母大写
        if re.fullmatch(r'[A-Za-z]{1,4}', token) and token[0].isupper():
            return True

        # 2) 多点缩写：U.S.A / F.B.I 这种（至少 3 个字母、2 个点）
        #    U.S.A -> token 为 'U.S.A'
        if re.fullmatch(r'[A-Za-z](?:\.[A-Za-z]){2,}', token):
            return True

        # 3) 你如果有特殊缩写，可以在这里硬编码
        # if token in {"etc", "e.g", "i.e"}:
        #     return True

        return False

    def split_sentences(self, text: str) -> List[str]:
        """按照标点符号进行细粒度分句，同时尽量保护英文缩写和数字。
        保留换行作为候选分句符。如果产生了“只有标点/引号”的句子，则直接丢弃。
        """
        # 规范化换行：把 \r\n 和 \r 统一为 \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 替换全角空格为普通空格，保留换行
        text = text.replace('\u3000', ' ').strip()

        # 分割：中文标点、特殊点号、或换行
        sentences = re.split(r'([。！？!?：；]|(?<!\d)\.(?!\d)|\n+)', text)

        result = []
        current_sentence = ""

        for part in sentences:
            if not part:
                continue

            current_sentence += part

            # 遇到句子结束符号时：
            if re.fullmatch(r'[。！？!?：；]', part) or part == '.' or re.fullmatch(r'\n+', part):
                if part == '.':
                    # 缩写保护
                    if self._looks_like_abbreviation(current_sentence):
                        continue

                # 清理末尾换行
                sent = current_sentence.strip()
                if re.fullmatch(r'\n+', part):
                    sent = re.sub(r'\n+$', '', sent).strip()

                # **关键：如果只有标点或引号，则直接跳过**
                if sent and not re.fullmatch(r'^[\s\W]+$', sent):
                    result.append(sent)

                current_sentence = ""

        # 末尾残余
        tail = current_sentence.strip()
        if tail and not re.fullmatch(r'^[\s\W]+$', tail):
            result.append(tail)

        return result

    def find_best_sentence_match(self, ai_sentence: str, original_sentences: List[str],
                                 start_index: int = 0, use_extended: bool = False) -> Tuple[Optional[int], float]:
        """在原文句子列表中找到与AI句子最匹配的单个句子。
        
        Args:
            ai_sentence: AI生成的句子
            original_sentences: 原文句子列表
            start_index: 搜索起始位置
            use_extended: 是否使用扩展搜索窗口
        
        Returns:
            (匹配索引, 相似度) 或 (None, 最高相似度)
        """
        # 预处理 - 使用专门的比较清理方法
        processed_ai_sentence = self.clean_for_compare(ai_sentence)
        if not processed_ai_sentence:
            return None, 0

        # 根据句子长度获取自适应阈值
        threshold = self.get_adaptive_threshold(ai_sentence)
        
        # 选择搜索窗口大小
        search_window = self.extended_window if use_extended else self.base_window

        best_match_index = None
        best_similarity = 0

        # 向前搜索
        end_index = min(start_index + search_window, len(original_sentences))
        for i in range(start_index, end_index):
            original_sentence = original_sentences[i]
            processed_original_sentence = self.clean_for_compare(original_sentence)

            if not processed_original_sentence:
                continue

            matcher = difflib.SequenceMatcher(None, processed_ai_sentence, processed_original_sentence)
            similarity = matcher.ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_index = i

        # 如果没找到匹配且未使用扩展窗口，尝试向后搜索（处理乱序情况）
        if best_similarity < threshold and not use_extended and start_index > 0:
            backward_start = max(0, start_index - 10)
            for i in range(backward_start, start_index):
                original_sentence = original_sentences[i]
                processed_original_sentence = self.clean_for_compare(original_sentence)

                if not processed_original_sentence:
                    continue

                matcher = difflib.SequenceMatcher(None, processed_ai_sentence, processed_original_sentence)
                similarity = matcher.ratio()

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_index = i

        if best_similarity < threshold:
            return None, best_similarity

        return best_match_index, best_similarity

    def correct_ai_text(self, original_text: str, ai_data: List[Dict]) -> List[Dict]:
        """使用分句匹配 + difflib 的方式校正AI文本。
        
        改进的算法：
        1. 记录每个校正后item对应的原文句子索引范围
        2. 基于实际索引位置插入遗漏句子
        3. 支持自适应搜索窗口
        """
        original_sentences = self.split_sentences(original_text)

        # 存储校正后的数据，以及每个item对应的原文索引范围
        corrected_data = []  # List of (item_dict, matched_indices_list)
        used_original_indices = set()
        current_original_index = 0

        for ai_item in ai_data:
            ai_text = ai_item.get('text_content', '')
            ai_sentences = self.split_sentences(ai_text)

            corrected_sentences_for_item = []
            matched_indices_for_item = []  # 记录这个item匹配到的所有原文索引

            logging.info("处理角色: %s (AI原文长度: %d)", ai_item.get('role_name', '未知'), len(ai_text) if ai_text else 0)
            # 详细内容仅 DEBUG 级别输出,避免 INFO 日志泄露过多内容
            logging.debug("AI原文: '%s'", ai_text[:50] if ai_text else '')

            for ai_sentence in ai_sentences:
                # 首先尝试基础窗口搜索
                match_index, similarity = self.find_best_sentence_match(
                    ai_sentence, original_sentences, current_original_index, use_extended=False
                )

                # 如果基础窗口没找到，尝试扩展窗口
                if match_index is None:
                    match_index, similarity = self.find_best_sentence_match(
                        ai_sentence, original_sentences, current_original_index, use_extended=True
                    )

                if match_index is not None:
                    original_match = original_sentences[match_index]
                    corrected_sentences_for_item.append(original_match)
                    matched_indices_for_item.append(match_index)
                    used_original_indices.add(match_index)
                    current_original_index = match_index + 1
                    # INFO 仅输出索引,DEBUG 输出具体内容
                    logging.info("匹配成功 (索引: %d, 相似度: %.2f)", match_index, similarity)
                    logging.debug("AI='%s' -> 原文='%s'", ai_sentence, original_match)
                else:
                    corrected_sentences_for_item.append(ai_sentence)
                    logging.warning("匹配失败 (最高相似度: %.2f),保留AI原句", similarity)
                    logging.debug("保留AI原句: '%s'", ai_sentence)

            # 最终清理 - 保留原始格式（包括引号）
            corrected_text = self.clean_text(" ".join(corrected_sentences_for_item))

            if corrected_text:
                corrected_item = ai_item.copy()
                corrected_item['text_content'] = corrected_text
                corrected_data.append((corrected_item, matched_indices_for_item))

        # 处理遗漏的原文句子 - 改进的插入逻辑
        missing_indices = set(range(len(original_sentences))) - used_original_indices
        
        if not missing_indices:
            # 没有遗漏，直接返回校正数据
            return [item for item, _ in corrected_data]

        logging.info("发现 %d 个遗漏句子，正在插入...", len(missing_indices))

        # 构建原文索引到校正item的映射
        # index_to_item_map: {原文索引: (corrected_item, item在corrected_data中的位置)}
        index_to_item = {}
        for item_idx, (item, matched_indices) in enumerate(corrected_data):
            for orig_idx in matched_indices:
                index_to_item[orig_idx] = (item, item_idx)

        # 按原文顺序构建最终结果
        final_data = []
        inserted_items = set()  # 记录已插入的item索引，避免重复插入

        for orig_idx in range(len(original_sentences)):
            if orig_idx in missing_indices:
                # 插入遗漏的句子
                missing_sentence = self.clean_text(original_sentences[orig_idx])
                if missing_sentence:
                    # INFO 仅输出索引,DEBUG 输出具体内容
                    logging.info("插入遗漏句子 (位置%d)", orig_idx)
                    logging.debug("插入遗漏句子内容: '%s'", missing_sentence)
                    final_data.append({
                        'role_name': '旁白',
                        'text_content': missing_sentence,
                        'emotion_name': '',
                        'strength_name': ''
                    })
            elif orig_idx in index_to_item:
                item, item_idx = index_to_item[orig_idx]
                # 只在第一次遇到这个item的匹配索引时插入
                if item_idx not in inserted_items:
                    final_data.append(item)
                    inserted_items.add(item_idx)

        # 处理可能没有匹配到任何原文索引但仍需要保留的item（纯AI生成内容）
        for item_idx, (item, matched_indices) in enumerate(corrected_data):
            if item_idx not in inserted_items:
                final_data.append(item)
                # INFO 仅输出索引,DEBUG 输出具体内容
                logging.warning("Item未匹配到原文,追加到末尾 (item_idx: %d)", item_idx)
                logging.debug("追加item内容: %s", item.get('text_content', '')[:30])

        return final_data
