<template>
  <div>
    <h2 style="margin-bottom:16px;">配置中心</h2>

    <el-tabs v-model="activeTab">
      <!-- LLM 管理 -->
      <el-tab-pane label="LLM 管理" name="llm">
        <div class="toolbar">
          <el-button type="primary" @click="openLLMDialog()">新增 LLM 提供商</el-button>
        </div>

        <el-table :data="llmList" stripe border highlight-current-row class="styled-table">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="api_base_url" label="Base URL" min-width="240" />
          <el-table-column prop="model_list" label="模型列表" min-width="240">
            <template #default="{ row }">
              <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;">
                <div style="display: flex; flex-wrap: wrap; gap: 4px; flex: 1;">
                  <el-tooltip
                    v-for="(item, idx) in (row.model_list || '').split(/[,，]/).filter(s => s.trim())"
                    :key="idx"
                    content="点击复制"
                    placement="top"
                    :show-after="500"
                  >
                    <el-tag
                      size="small"
                      effect="plain"
                      style="cursor: pointer;"
                      @click="copyText(item.trim())"
                    >
                      {{ item.trim() }}
                    </el-tag>
                  </el-tooltip>
                </div>
                <el-tooltip content="复制全部模型" placement="top">
                  <el-button
                    type="info"
                    link
                    :icon="CopyDocument"
                    @click="copyText(row.model_list)"
                    style="padding: 0; height: auto;"
                  />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="API Key" min-width="180">
            <template #default="{ row }">
              <span class="api-key">{{ maskKey(row.api_key) }}</span>
            </template>
          </el-table-column>



          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag effect="light" :type="row.status === 1 ? 'success' : 'info'">
                <span class="status-dot" :class="row.status === 1 ? 'dot-green' : 'dot-gray'"></span>
                {{ row.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>

          <!-- <el-table-column prop="updated_at" label="更新于" min-width="180" /> -->

          <el-table-column label="操作" width="180" fixed="right" align="center">
            <template #default="{ row }">
              <div class="flex justify-center gap-2">
                <el-button type="primary" size="small" plain @click="openLLMDialog(row)">
                  编辑
                </el-button>

                <el-popconfirm title="确认删除该 LLM 提供商？" confirm-button-text="确定" cancel-button-text="取消"
                  @confirm="removeLLM(row.id)">
                  <template #reference>
                    <el-button type="danger" size="small" plain>
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>

        </el-table>
      </el-tab-pane>

      <!-- TTS 管理 -->
      <el-tab-pane label="TTS 管理" name="tts">
        <div class="toolbar">
          <el-button type="primary" @click="openTTSDialog()">新增 TTS 提供商</el-button>
        </div>

        <el-table :data="ttsList" stripe border highlight-current-row class="styled-table">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column label="TTS 类型" min-width="140">
            <template #default="{ row }">
              <el-tag :type="row.provider_type === 'index_tts' ? 'success' : row.provider_type === 'volcano' ? 'warning' : 'danger'" size="small">
                {{ row.provider_type === 'index_tts' ? 'IndexTTS' : row.provider_type === 'volcano' ? '火山引擎' : '阿里云' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="地域/模型" min-width="200">
            <template #default="{ row }">
              <template v-if="row.provider_type === 'aliyun'">
                <el-tag size="small" type="info">{{ row.api_base_url || 'cosyvoice-v3-plus' }}</el-tag>
              </template>
              <template v-else>
                {{ row.api_base_url }}
              </template>
            </template>
          </el-table-column>
          <el-table-column prop="resource_id" label="资源 ID" min-width="140" />
          <el-table-column prop="voice_type" label="音色" min-width="180" />

          <el-table-column label="API Key" min-width="180">
            <template #default="{ row }">
              <span class="api-key">{{ maskKey(row.api_key) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag effect="light" :type="row.status === 1 ? 'success' : 'info'">
                <span class="status-dot" :class="row.status === 1 ? 'dot-green' : 'dot-gray'"></span>
                {{ row.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="180" fixed="right" align="center">
            <template #default="{ row }">
              <div class="flex justify-center gap-2">
                <el-button type="primary" size="small" plain @click="openTTSDialog(row)">
                  编辑
                </el-button>

                <el-popconfirm title="确认删除该 TTS 提供商？" confirm-button-text="确定" cancel-button-text="取消"
                  @confirm="removeTTS(row.id)">
                  <template #reference>
                    <el-button type="danger" size="small" plain>
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- LLM 弹窗 -->
    <el-dialog :title="llmForm.id ? '编辑 LLM 提供商' : '新增 LLM 提供商'" v-model="llmDialogVisible" width="560px">
      <el-form :model="llmForm" :rules="llmRules" ref="llmFormRef" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="llmForm.name" placeholder="如：DeepSeek" />
        </el-form-item>
        <el-form-item label="Base URL" prop="api_base_url">
          <el-input v-model="llmForm.api_base_url" placeholder="https://api.xxx.com" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="llmForm.api_key" placeholder="可留空" show-password />
        </el-form-item>
        <el-form-item label="模型列表">
          <el-select
            v-model="currentModelList"
            multiple
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            placeholder="输入模型后回车，或从下拉选择"
            style="width: 100%"
          >
            <el-option-group
              v-if="presetModelOptions.length > 0"
              :label="presetModelLabel"
            >
              <el-option
                v-for="m in presetModelOptions"
                :key="m.value"
                :label="m.label"
                :value="m.value"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="llmForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="自定义参数" prop="custom_params">
          <el-input type="textarea" v-model="llmForm.custom_params" :rows="6" placeholder='请输入 JSON 格式参数' />
        </el-form-item>

      </el-form>

      <template #footer>
        <!-- 新增测试按钮 -->
        <el-button type="warning" @click="testLLM">测试</el-button>
        <el-button @click="llmDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLLM">确定</el-button>
      </template>
    </el-dialog>

    <!-- TTS 弹窗（新增/编辑） -->
    <el-dialog :title="ttsForm.id ? '编辑 TTS 引擎' : '新增 TTS 引擎'" v-model="ttsDialogVisible" width="600px">
      <el-form :model="ttsForm" :rules="ttsRules" ref="ttsFormRef" label-width="120px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="ttsForm.name" placeholder="如：Index_TTS" />
        </el-form-item>

        <el-form-item label="TTS 类型" prop="provider_type">
          <el-select v-model="ttsForm.provider_type" placeholder="选择 TTS 类型" style="width: 100%" @change="onTtsTypeChange">
            <el-option label="IndexTTS (自部署)" value="index_tts" />
            <el-option label="火山引擎" value="volcano" />
            <el-option label="阿里云" value="aliyun" />
          </el-select>
        </el-form-item>

        <!-- IndexTTS 专属字段 -->
        <template v-if="ttsForm.provider_type === 'index_tts'">
          <el-form-item label="Base URL">
            <el-input v-model="ttsForm.api_base_url" placeholder="http://127.0.0.1:8000" />
          </el-form-item>
        </template>

        <!-- 云 TTS 专属字段 -->
        <template v-if="ttsForm.provider_type === 'volcano' || ttsForm.provider_type === 'aliyun'">
          <el-form-item v-if="ttsForm.provider_type === 'aliyun'" label="CosyVoice 模型" prop="api_base_url">
            <el-select v-model="ttsForm.api_base_url" placeholder="选择 CosyVoice 模型" style="width: 100%" filterable>
              <el-option v-for="model in aliyunModels" :key="model.value" :label="model.label" :value="model.value" />
            </el-select>
          </el-form-item>

          <!-- 火山引擎特有字段 -->
          <template v-if="ttsForm.provider_type === 'volcano'">
            <el-form-item label="X-Api-Key" prop="x_api_key">
              <el-input v-model="ttsForm.x_api_key" type="password" show-password placeholder="请输入 X-Api-Key（新版鉴权，推荐）" />
            </el-form-item>
            <el-form-item label="资源 ID" prop="resource_id">
              <el-select v-model="ttsForm.resource_id" placeholder="选择资源 ID" style="width: 100%" filterable allow-create>
                <el-option label="语音合成 2.0（seed-tts-2.0）" value="seed-tts-2.0" />
                <el-option label="语音合成 1.0（seed-tts-1.0）" value="seed-tts-1.0" />
                <el-option label="语音合成 1.0 并发版（seed-tts-1.0-concurr）" value="seed-tts-1.0-concurr" />
                <el-option label="声音复刻 2.0（seed-icl-2.0）" value="seed-icl-2.0" />
                <el-option label="声音复刻 1.0（seed-icl-1.0）" value="seed-icl-1.0" />
                <el-option label="声音复刻 1.0 并发版（seed-icl-1.0-concurr）" value="seed-icl-1.0-concurr" />
              </el-select>
            </el-form-item>
            <el-form-item label="音色/Speaker" prop="voice_type">
              <el-input v-model="ttsForm.voice_type" placeholder="请输入音色名称，如 zh_female_shuangkuaisisi_moon_bigtts" />
            </el-form-item>
            <el-form-item label="AppID（语音复刻）" prop="voice_clone_appid">
              <el-input v-model="ttsForm.voice_clone_appid" placeholder="请输入火山引擎应用 AppID（用于语音复刻功能）" />
            </el-form-item>
            <el-form-item label="AccessKey ID" prop="access_key_id">
              <el-input v-model="ttsForm.access_key_id" placeholder="请输入火山引擎 AccessKey ID（用于查询音色列表）" />
            </el-form-item>
            <el-form-item label="AccessKey Secret" prop="access_key_secret">
              <el-input v-model="ttsForm.access_key_secret" type="password" show-password placeholder="请输入火山引擎 AccessKey Secret（用于查询音色列表）" />
            </el-form-item>
          </template>

          <el-form-item v-if="ttsForm.provider_type === 'aliyun'" label="DashScope API Key">
            <el-input v-model="ttsForm.api_key" type="password" show-password placeholder="请输入 DashScope API Key（用于语音合成和声音复刻）" />
          </el-form-item>

          <el-form-item v-if="ttsForm.provider_type === 'aliyun'" label="音色" prop="voice_type">
            <el-select v-model="ttsForm.voice_type" placeholder="选择音色" style="width: 100%" filterable>
              <el-option v-for="voice in currentVoices" :key="voice.value" :label="voice.label" :value="voice.value" />
            </el-select>
          </el-form-item>
        </template>

        <el-form-item label="状态">
          <el-switch v-model="ttsForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>

      </el-form>

      <template #footer>
        <el-button type="warning" @click="testTTS">测试</el-button>
        <el-button @click="ttsDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTTS">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>



<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument } from '@element-plus/icons-vue'
import {
  fetchLLMProviders, createLLMProvider, updateLLMProvider, deleteLLMProvider,
  fetchTTSProviders, createTTSProvider, updateTTSProvider, deleteTTSProvider, testLLMProvider, testTTSProvider
} from '../api/provider'

const activeTab = ref('llm')

// ---------- LLM ----------
const llmList = ref([])

const loadLLM = async () => { llmList.value = await fetchLLMProviders() }

const llmDialogVisible = ref(false)
const llmFormRef = ref()
const DEFAULT_CUSTOM_PARAMS = JSON.stringify(
  {
    response_format: { type: 'json_object' },
    temperature: 0.7,
    top_p: 0.9
  },
  null,
  2  // 漂亮一点，换行缩进
)

const llmForm = ref({
  id: null,
  name: '',
  api_base_url: '',
  api_key: '',
  model_list: '',
  status: 1,
  custom_params: DEFAULT_CUSTOM_PARAMS
})
const llmRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  api_base_url: [{ required: true, message: '请输入 Base URL', trigger: 'blur' }],
  custom_params: [
    {
      required: true,
      message: '自定义参数不能为空，至少为 {}',
      trigger: 'blur'
    },
    {
      validator: (rule, value, callback) => {
        const v = (value || '').trim()
        if (!v) {
          return callback(new Error('自定义参数不能为空，至少为 {}'))
        }
        try {
          JSON.parse(v)
          callback()
        } catch (e) {
          callback(new Error('自定义参数必须是合法 JSON 格式'))
        }
      },
      trigger: 'blur'
    }
  ]
}

const currentModelList = ref([])

// ========== 预置模型列表（Qwen 系列） ==========
const qwenModels = [
  { label: 'qwen-turbo（通义千问-Turbo）', value: 'qwen-turbo' },
  { label: 'qwen-plus（通义千问-Plus）', value: 'qwen-plus' },
  { label: 'qwen-max（通义千问-Max）', value: 'qwen-max' },
  { label: 'qwen-max-latest（通义千问-Max 最新）', value: 'qwen-max-latest' },
  { label: 'qwen-plus-latest（通义千问-Plus 最新）', value: 'qwen-plus-latest' },
  { label: 'qwen-turbo-latest（通义千问-Turbo 最新）', value: 'qwen-turbo-latest' },
  { label: 'qwen-long（长文本）', value: 'qwen-long' },
  { label: 'qwen3-235b-a22b', value: 'qwen3-235b-a22b' },
  { label: 'qwen3-30b-a3b', value: 'qwen3-30b-a3b' },
  { label: 'qwen3-32b', value: 'qwen3-32b' },
  { label: 'qwen3-14b', value: 'qwen3-14b' },
  { label: 'qwen3-8b', value: 'qwen3-8b' },
  { label: 'qwen3-4b', value: 'qwen3-4b' },
  { label: 'qwen3-1.7b', value: 'qwen3-1.7b' },
  { label: 'qwen3-0.6b', value: 'qwen3-0.6b' },
  { label: 'qwq-plus（推理增强）', value: 'qwq-plus' },
  { label: 'qwen-vl-max（视觉理解）', value: 'qwen-vl-max' },
  { label: 'qwen-vl-plus（视觉理解）', value: 'qwen-vl-plus' },
]

const presetModelOptions = computed(() => qwenModels)
const presetModelLabel = computed(() => 'Qwen（通义千问）')

// 监听弹窗打开，初始化 currentModelList
watch(() => llmDialogVisible.value, (val) => {
  if (val) {
    if (llmForm.value.model_list) {
      currentModelList.value = llmForm.value.model_list
        .split(/[,，]/)
        .map(s => s.trim())
        .filter(s => s)
    } else {
      currentModelList.value = []
    }
  } else {
    currentModelList.value = []
  }
})

// 监听 currentModelList 变化，同步回 llmForm.model_list
let isUpdatingModelList = false // 防止 watch 递归触发
watch(currentModelList, (val) => {
  if (isUpdatingModelList) return
  // 如果输入包含逗号，自动分割
  let hasSplit = false
  const processedList = []

  for (const item of val) {
    if (item && (item.includes(',') || item.includes('，'))) {
      const parts = item.split(/[,，]/).map(s => s.trim()).filter(s => s)
      processedList.push(...parts)
      hasSplit = true
    } else {
      processedList.push(item)
    }
  }

  if (hasSplit) {
    // 去重并更新 currentModelList
    isUpdatingModelList = true
    currentModelList.value = [...new Set(processedList)]
    isUpdatingModelList = false
    return
  }

  llmForm.value.model_list = val.join(',')
}, { deep: true })

const copyText = (text) => {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function openLLMDialog(row) {
  if (row) llmForm.value = { ...row }
  else llmForm.value = { id: null, name: '', api_base_url: '', api_key: '', model_list: '', status: 1, custom_params: DEFAULT_CUSTOM_PARAMS }
  llmDialogVisible.value = true
}
function submitLLM() {
  llmFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      if (llmForm.value.id) {
        await updateLLMProvider(llmForm.value.id, llmForm.value)
        ElMessage.success('已更新')
      } else {
        await createLLMProvider(llmForm.value)
        ElMessage.success('已创建')
      }
      llmDialogVisible.value = false
      await loadLLM()
    } catch {
      ElMessage.error('操作失败')
    }
  })
}
async function removeLLM(id) {
  try {
    await deleteLLMProvider(id)
    ElMessage.success('已删除')
    await loadLLM()
  } catch {
    ElMessage.error('删除失败')
  }
}


import { ElLoading } from 'element-plus'

async function testLLM() {
  // 打开等待框
  const loading = ElLoading.service({
    lock: true,
    text: '正在测试，请稍候...',
    background: 'rgba(0, 0, 0, 0.4)'
  })

  try {
    const res = await testLLMProvider(llmForm.value)
    if (res.code === 200) {
      ElMessage.success(res.message || '测试成功')
    } else {
      ElMessage.error(res.message || '测试失败')
    }
  } catch (e) {
    ElMessage.error('测试异常')
  } finally {
    // 关闭等待框
    loading.close()
  }
}



// ---------- TTS ----------
const ttsList = ref([])
const ttsDialogVisible = ref(false)
const ttsFormRef = ref()

const aliyunRegions = [
  { label: "上海", value: "cn-shanghai" },
  { label: "北京", value: "cn-beijing" },
  { label: "杭州", value: "cn-hangzhou" },
  { label: "深圳", value: "cn-shenzhen" },
]

const aliyunModels = [
  { label: "CosyVoice-V3-Plus（高质量）", value: "cosyvoice-v3-plus" },
  { label: "CosyVoice-V3.5-Plus（高质量）", value: "cosyvoice-v3.5-plus" },
  { label: "CosyVoice-V3.5-Flash（快速）", value: "cosyvoice-v3.5-flash" },
  { label: "CosyVoice-V3-Flash（快速）", value: "cosyvoice-v3-flash" },
]

const volcanoVoices = ref([])

const aliyunVoices = [
  { label: "龙小淳 (CosyVoice)", value: "longxiaochun" },
  { label: "龙小春", value: "longxiaochunv2" },
  { label: "龙言", value: "longyan" },
  { label: "龙悦", value: "longyue" },
  { label: "龙清", value: "longqing" },
]

const ttsForm = ref({
  id: null,
  name: '',
  provider_type: 'aliyun',
  api_base_url: '',
  api_key: '',
  x_api_key: '',
  voice_type: '',
  resource_id: '',
  access_key_id: '',
  access_key_secret: '',
  voice_clone_appid: '',
  status: 1,
})

const currentRegions = ref([])
const currentVoices = ref([])

const onTtsTypeChange = () => {
  if (ttsForm.value.provider_type === 'volcano') {
    currentRegions.value = []
    currentVoices.value = volcanoVoices.value
  } else if (ttsForm.value.provider_type === 'aliyun') {
    currentRegions.value = aliyunRegions
    currentVoices.value = aliyunVoices
    // 设置默认模型（如果为空或还是旧的地域值）
    const currentVal = ttsForm.value.api_base_url
    const validModels = aliyunModels.map(m => m.value)
    if (!currentVal || !validModels.includes(currentVal)) {
      ttsForm.value.api_base_url = 'cosyvoice-v3-plus'
    }
  } else {
    currentRegions.value = []
    currentVoices.value = []
  }
}

// 阿里云现在使用 DashScope API Key，不需要拆分/组合
// 保留 parseApiKey/buildApiKey 中的 aliyun 分支仅做直接 return

const parseApiKey = () => {
  if (ttsForm.value.provider_type === 'volcano') {
    if (ttsForm.value.api_key && ttsForm.value.api_key.includes(':')) {
      const parts = ttsForm.value.api_key.split(':')
      ttsForm.value.access_key_id = parts[0]
      ttsForm.value.access_key_secret = parts.slice(1).join(':')
    } else {
      ttsForm.value.access_key_id = ''
      ttsForm.value.access_key_secret = ''
    }
  } else {
    // aliyun:直接使用 DashScope API Key,无需拆分
    return
  }
}

const buildVolcanoKey = () => {
  const akid = ttsForm.value.access_key_id || ''
  const aks = ttsForm.value.access_key_secret || ''
  if (akid && aks) {
    ttsForm.value.api_key = `${akid}:${aks}`
  } else {
    ttsForm.value.api_key = ''
  }
}

const buildApiKey = () => {
  if (ttsForm.value.provider_type === 'volcano') {
    buildVolcanoKey()
  } else {
    // aliyun:直接使用 DashScope API Key,无需组合
    return
  }
}

const ttsRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  provider_type: [{ required: true, message: '请选择 TTS 类型', trigger: 'change' }],
}

const loadTTS = async () => {
  const list = await fetchTTSProviders()
  ttsList.value = Array.isArray(list) ? list : []
}

function openTTSDialog(row) {
  if (row) {
    ttsForm.value = { ...row, provider_type: row.provider_type || 'aliyun' }
  } else {
    ttsForm.value = {
      id: null,
      name: '',
      provider_type: 'aliyun',
      api_base_url: '',
      api_key: '',
      x_api_key: '',
      voice_type: '',
      resource_id: '',
      access_key_id: '',
      access_key_secret: '',
      voice_clone_appid: '',
      status: 1,
    }
  }
  parseApiKey()
  onTtsTypeChange()
  ttsDialogVisible.value = true
}

function submitTTS() {
  ttsFormRef.value.validate(async (valid) => {
    if (!valid) return
    buildApiKey()
    try {
      if (ttsForm.value.id) {
        await updateTTSProvider(ttsForm.value.id, ttsForm.value)
        ElMessage.success('已更新')
      } else {
        await createTTSProvider(ttsForm.value)
        ElMessage.success('已创建')
      }
      ttsDialogVisible.value = false
      await loadTTS()
    } catch {
      ElMessage.error('操作失败')
    }
  })
}



async function testTTS() {
  const loading = ElLoading.service({
    lock: true,
    text: '正在测试 TTS，请稍候...',
    background: 'rgba(0, 0, 0, 0.4)'
  })

  try {
    buildApiKey()
    const res = await testTTSProvider(ttsForm.value)
    if (res.code === 200) {
      ElMessage.success(res.message || 'TTS 测试成功')
    } else {
      ElMessage.error(res.message || 'TTS 测试失败')
    }
  } catch (e) {
    ElMessage.error('TTS 测试异常')
  } finally {
    loading.close()
  }
}

async function removeTTS(id) {
  try {
    await deleteTTSProvider(id)
    ElMessage.success('已删除')
    await loadTTS()
  } catch {
    ElMessage.error('删除失败')
  }
}



// ---------- 工具 ----------
const maskKey = (val) => (val ? '•'.repeat(Math.min(val.length, 8)) : '（未设置）')

onMounted(async () => {
  await Promise.all([loadLLM(), loadTTS()])
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}

.masked {
  margin-right: 8px;
}

.styled-table {
  border-radius: 10px;
  overflow: hidden;
  font-size: 14px;
}

.styled-table ::v-deep(.el-table__header th) {
  background-color: var(--el-fill-color-light);
  font-weight: 600;
  text-align: center;
}

.styled-table ::v-deep(.el-table__body td) {
  text-align: center;
}

.api-key {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.dot-green {
  background: #67c23a;
}

.dot-gray {
  background: #909399;
}
</style>
