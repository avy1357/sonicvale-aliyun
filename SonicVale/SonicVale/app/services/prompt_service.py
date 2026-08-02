from sqlalchemy import select, func
from typing import Sequence

from app.core.enums import TaskEnum
from app.core.llm_engine import LLMEngine
from app.core.prompts import get_prompt_str
from app.entity.prompt_entity import PromptEntity
from app.models.po import PromptPO, ProjectPO

from app.repositories.prompt_repository import PromptRepository


class PromptService:

    def __init__(self, repository: PromptRepository):
        """注入 repository"""
        self.repository = repository

    # 拆分台词prompt验证
    def validate_prompt_with_DUBBING(self, content: str):
        # content 为 None/空时直接返回 False,避免 in 操作符对 None 报错
        if not content:
            return False
        REQUIRED_BLOCKS = [
            # ("<possible_characters>", "</possible_characters>", "{possible_characters}"),
            # ("<possible_emotions>", "</possible_emotions>", "{possible_emotions}"),
            # ("<possible_strengths>", "</possible_strengths>", "{possible_strengths}"),
            ("<novel_content>", "</novel_content>", "{novel_content}"),
        ]
        for start, end, placeholder in REQUIRED_BLOCKS:
            if start not in content or end not in content or placeholder not in content:
                return False
        return  True

    # 创建默认提示词
    def create_default_prompt(self):
        task = TaskEnum.DUBBING
        name = "默认拆分台词提示词"
        description = "默认拆分台词提示词"
        content = get_prompt_str()
        self.create_prompt(PromptEntity(name=name, description=description, content=content, task=task))
        return True

    def create_prompt(self,  entity: PromptEntity):
        """创建新提示词
        - 检查同名提示词是否存在
        - 如果存在，抛出异常或返回错误
        - 调用 repository.create 插入数据库
        """
        prompt = self.repository.get_by_name(entity.name)
        if prompt:
            return None
        # 判断task是否存在于task_enum中
        if entity.task not in TaskEnum:
            return None

        # 验证拆分台词的提示词
        if entity.task == TaskEnum.DUBBING:
            isValid = self.validate_prompt_with_DUBBING(entity.content)
            if not isValid:
                return None

        # 手动将entity转化为po
        po = PromptPO(**entity.__dict__)
        res = self.repository.create(po)

        # res(po) --> entity
        data = {k: v for k, v in res.__dict__.items() if not k.startswith("_")}
        entity = PromptEntity(**data)

        # 将po转化为entity
        return entity


    def get_prompt(self, prompt_id: int) -> PromptEntity | None:
        """根据 ID 查询提示词"""
        po = self.repository.get_by_id(prompt_id)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        res = PromptEntity(**data)
        return res

    def get_all_prompts(self) -> Sequence[PromptEntity]:
        """获取所有提示词列表"""
        pos = self.repository.get_all()
        # pos -> entities

        entities = [
            PromptEntity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")})
            for po in pos
        ]
        return entities

    def update_prompt(self, prompt_id: int, data:dict) -> bool:
        """更新提示词
        - 可以只更新部分字段
        - 检查同名冲突
        """
        name = data.get("name")
        if name:
            existing = self.repository.get_by_name(name)
            if existing and existing.id != prompt_id:
                return False
        # 如果改的是content
        task = data.get("task")
        if task:
            try:
                task = TaskEnum(task)
            except ValueError:
                return False
        # task 为 None 时,查询原记录的 task 进行判断,避免跳过 DUBBING 校验
        if task is None:
            original = self.repository.get_by_id(prompt_id)
            if original and original.task:
                try:
                    task = TaskEnum(original.task)
                except ValueError:
                    task = None
        if task == TaskEnum.DUBBING:
            content = data.get("content")
            # content 为 None 时表示未修改 content,查询原记录
            if content is None:
                original = self.repository.get_by_id(prompt_id)
                content = original.content if original else None
            if not self.validate_prompt_with_DUBBING(content=content):
                return False

        self.repository.update(prompt_id, data)
        return True

    def delete_prompt(self, prompt_id: int) -> bool:
        """删除提示词
        - 删除前检查是否被 project 引用,被引用则禁止删除
        """
        db = self.repository.db
        # 检查是否有 project 引用了该提示词
        count = db.execute(
            select(func.count()).select_from(ProjectPO).where(
                ProjectPO.prompt_id == prompt_id
            )
        ).scalar_one()
        if count and count > 0:
            return False
        res = self.repository.delete(prompt_id)
        return res
    # 根据task 获取提示词列表
    def get_prompt_by_task(self, task: str) -> Sequence[PromptEntity]:
        pos = self.repository.get_by_task(task)
        entities = [
            PromptEntity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")})
            for po in pos
        ]
        return entities

    # 获取所有的stak
    def get_all_tasks(self) -> Sequence[str]:
        # 这些写死了，后面也在这添加，不改成数据库
        return list(TaskEnum)


    # def test_prompt(self, entity: PromptEntity):
    #     """测试提示词"""
    #     # 按逗号划分模型名称
    #     if entity.api_base_url is None or entity.api_key is None or entity.model_list is None:
    #         return False
    #     model_lists = entity.model_list.split(",")
    #     llm = LLMEngine(entity.api_key, entity.api_base_url, model_lists[0])
    #     res = llm.generate_text_test("你好")
    #     if res is not None:
    #         return True
    #     return False

#     根据名字获取提示词
    def get_prompt_by_name(self, name: str) -> PromptEntity | None:
        """根据名字获取提示词"""
        po = self.repository.get_by_name(name)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        res = PromptEntity(**data)
        return res




