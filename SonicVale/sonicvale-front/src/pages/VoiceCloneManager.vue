<template>
  <div>
    <h2 style="margin-bottom:16px;">声音复刻管理</h2>
    
    <div class="toolbar">
      <el-select v-model="selectedTtsId" placeholder="选择 TTS 提供商" style="width: 300px; margin-right: 12px;" @change="onTtsChange">
        <el-option-group label="火山引擎">
          <el-option v-for="tts in volcanoTtsList" :key="'volcano-' + tts.id" :label="tts.name" :value="'volcano-' + tts.id" />
        </el-option-group>
        <el-option-group label="阿里云">
          <el-option v-for="tts in aliyunTtsList" :key="'aliyun-' + tts.id" :label="tts.name" :value="'aliyun-' + tts.id" />
        </el-option-group>
      </el-select>
      <el-button type="primary" @click="openCreateDialog" :disabled="!selectedTtsId">新增声音复刻</el-button>
      <el-button v-if="currentProviderType === 'aliyun'" type="success" @click="refreshList" :disabled="!selectedTtsId">刷新列表</el-button>
      <el-button v-if="currentProviderType === 'aliyun'" type="warning" @click="handleSyncAll" :disabled="!selectedTtsId">全部同步</el-button>
    </div>

    <el-table :data="cloneList" stripe border v-if="cloneList.length > 0">
      <el-table-column label="来源" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="currentProviderType === 'volcano'" type="warning" size="small">火山引擎</el-tag>
          <el-tag v-else-if="currentProviderType === 'aliyun'" type="primary" size="small">阿里云</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="currentProviderType === 'volcano'" prop="name" label="音色名称" min-width="150" />
      <el-table-column v-if="currentProviderType === 'volcano'" prop="speaker_id" label="Speaker ID" min-width="180" />
      <el-table-column v-if="currentProviderType === 'volcano'" label="模型类型" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="getModelTypeTag(row.model_type)">
            {{ getModelTypeName(row.model_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="currentProviderType === 'volcano'" label="训练状态" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="getStatusTag(row.status)">
            {{ getStatusName(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="currentProviderType === 'volcano'" prop="version" label="版本" width="80" />
      
      <el-table-column v-if="currentProviderType === 'aliyun'" prop="voice_id" label="Voice ID" min-width="280" />
      <el-table-column v-if="currentProviderType === 'aliyun'" prop="name" label="名称" min-width="150" />
      <el-table-column v-if="currentProviderType === 'aliyun'" prop="target_model" label="模型" min-width="150" />
      <el-table-column v-if="currentProviderType === 'aliyun'" prop="language_hints" label="语种" width="120" />
      <el-table-column v-if="currentProviderType === 'aliyun'" label="预处理" width="80" align="center">
        <template #default="{ row }">
          {{ row.enable_preprocess ? '已开启' : '未开启' }}
        </template>
      </el-table-column>

      <el-table-column label="操作" :width="currentProviderType === 'volcano' ? 300 : 260" fixed="right">
        <template #default="{ row }">
          <template v-if="currentProviderType === 'volcano'">
            <el-button size="small" @click="openUploadDialog(row)" :disabled="row.status === 1">上传训练</el-button>
            <el-button size="small" @click="refreshStatus(row)" :disabled="row.status !== 1">刷新状态</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
          <template v-else-if="currentProviderType === 'aliyun'">
            <el-button size="small" type="primary" @click="viewDetail(row)">查看详情</el-button>
            <el-button size="small" type="success" @click="handleSyncSingle(row)">同步到本地</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else-if="selectedTtsId" description="暂无声音复刻记录" />
    <el-empty v-else description="请先选择 TTS 提供商" />

    <el-pagination
      v-if="currentProviderType === 'aliyun' && cloneList.length > 0"
      style="margin-top: 16px; text-align: right;"
      background
      layout="total, prev, pager, next"
      :total="aliyunTotal"
      :current-page="aliyunPage"
      :page-size="aliyunPageSize"
      @current-change="handlePageChange"
    />

    <el-dialog :title="'新增声音复刻'" v-model="createDialogVisible" width="600px">
      <el-form :model="createForm" label-width="120px">
        <template v-if="currentProviderType === 'volcano'">
          <el-form-item label="音色名称">
            <el-input v-model="createForm.name" placeholder="如：我的声音" />
          </el-form-item>
          <el-form-item label="Speaker ID">
            <el-input v-model="createForm.speaker_id" placeholder="S_开头，从控制台获取" />
          </el-form-item>
          <el-form-item label="模型类型">
            <el-select v-model="createForm.model_type" style="width: 100%">
              <el-option label="ICL 1.0" :value="1" />
              <el-option label="DiT 标准版" :value="2" />
              <el-option label="DiT 还原版" :value="3" />
              <el-option label="ICL 2.0" :value="4" />
            </el-select>
          </el-form-item>
          <el-form-item label="语种">
            <el-select v-model="createForm.language" style="width: 100%">
              <el-option label="中文" :value="0" />
              <el-option label="英文" :value="1" />
              <el-option label="日语" :value="2" />
            </el-select>
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="createForm.description" type="textarea" :rows="3" />
          </el-form-item>
        </template>
        <template v-else-if="currentProviderType === 'aliyun'">
          <el-form-item label="目标模型" required>
            <el-select v-model="createForm.target_model" style="width: 100%" @change="onTargetModelChange">
              <el-option label="cosyvoice-v3-plus" value="cosyvoice-v3-plus" />
              <el-option label="cosyvoice-v3.5-plus" value="cosyvoice-v3.5-plus" />
              <el-option label="cosyvoice-v3.5-flash" value="cosyvoice-v3.5-flash" />
              <el-option label="cosyvoice-v3-flash" value="cosyvoice-v3-flash" />
            </el-select>
          </el-form-item>
          <el-form-item label="音色前缀" required>
            <el-input v-model="createForm.prefix" placeholder="数字和英文字母，不超过10个字符" maxlength="10" />
          </el-form-item>
          <el-form-item label="音频URL" required>
            <el-input v-model="createForm.url" placeholder="公网可访问的音频文件URL" />
          </el-form-item>
          <el-form-item label="语种">
            <el-select v-model="createForm.language_hints" multiple placeholder="可多选，支持的语种">
              <el-option v-for="lang in currentLanguageOptions" :key="lang.value" :label="lang.label" :value="lang.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="参考音频时长">
            <el-input-number v-model="createForm.max_prompt_audio_length" :min="3" :max="30" :step="1" />
            <span style="margin-left: 8px; color: #909399;">秒（3-30秒）</span>
          </el-form-item>
          <el-form-item label="音频预处理">
            <el-switch v-model="createForm.enable_preprocess" />
            <span style="margin-left: 8px; color: #909399;">有背景噪音时建议开启</span>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="'上传训练 - ' + currentClone.name" v-model="uploadDialogVisible" width="500px">
      <el-form :model="uploadForm" label-width="120px">
        <el-form-item label="音频文件路径">
          <el-input v-model="uploadForm.reference_path" placeholder="本地音频文件完整路径" />
        </el-form-item>
        <el-form-item label="参考文本">
          <el-input v-model="uploadForm.text" type="textarea" :rows="2" placeholder="可选，音频朗读的内容" />
        </el-form-item>
        <el-form-item label="降噪">
          <el-switch v-model="uploadForm.enable_denoise" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload">开始训练</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="'音色详情'" v-model="detailDialogVisible" width="600px">
      <el-descriptions v-if="currentDetail" :column="2" border>
        <el-descriptions-item label="Voice ID">{{ currentDetail.voice_id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ currentDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="目标模型">{{ currentDetail.target_model }}</el-descriptions-item>
        <el-descriptions-item label="语种">{{ currentDetail.language_hints?.join(', ') }}</el-descriptions-item>
        <el-descriptions-item label="参考音频时长">{{ currentDetail.max_prompt_audio_length }}秒</el-descriptions-item>
        <el-descriptions-item label="音频预处理">{{ currentDetail.enable_preprocess ? '已开启' : '未开启' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchTTSProviders } from '../api/provider'
import { 
  fetchVoiceClones, createVoiceClone, deleteVoiceClone,
  uploadAudio, queryStatus 
} from '../api/voice_clone'
import {
  queryAliyunVoiceList,
  getAliyunVoiceDetail,
  createAliyunVoice,
  deleteAliyunVoice,
  syncAliyunVoices,
  syncAliyunVoiceSingle
} from '../api/aliyun_voice_clone'

// 模型对应的语种映射
const MODEL_LANGUAGE_MAP = {
  'cosyvoice-v3-plus': [
    { label: '中文', value: 'zh' },
    { label: '英文', value: 'en' },
    { label: '法语', value: 'fr' },
    { label: '德语', value: 'de' },
    { label: '日语', value: 'ja' },
    { label: '韩语', value: 'ko' },
    { label: '俄语', value: 'ru' },
  ],
  'cosyvoice-v3.5-plus': [
    { label: '中文', value: 'zh' },
    { label: '英文', value: 'en' },
    { label: '法语', value: 'fr' },
    { label: '德语', value: 'de' },
    { label: '日语', value: 'ja' },
    { label: '韩语', value: 'ko' },
    { label: '俄语', value: 'ru' },
    { label: '葡萄牙语', value: 'pt' },
    { label: '泰语', value: 'th' },
    { label: '印尼语', value: 'id' },
    { label: '越南语', value: 'vi' },
  ],
  'cosyvoice-v3.5-flash': [
    { label: '中文', value: 'zh' },
    { label: '英文', value: 'en' },
    { label: '法语', value: 'fr' },
    { label: '德语', value: 'de' },
    { label: '日语', value: 'ja' },
    { label: '韩语', value: 'ko' },
    { label: '俄语', value: 'ru' },
    { label: '葡萄牙语', value: 'pt' },
    { label: '泰语', value: 'th' },
    { label: '印尼语', value: 'id' },
    { label: '越南语', value: 'vi' },
  ],
  'cosyvoice-v3-flash': [
    { label: '中文', value: 'zh' },
    { label: '英文', value: 'en' },
    { label: '法语', value: 'fr' },
    { label: '德语', value: 'de' },
    { label: '日语', value: 'ja' },
    { label: '韩语', value: 'ko' },
    { label: '俄语', value: 'ru' },
    { label: '葡萄牙语', value: 'pt' },
    { label: '泰语', value: 'th' },
    { label: '印尼语', value: 'id' },
    { label: '越南语', value: 'vi' },
  ],
}

const volcanoTtsList = ref([])
const aliyunTtsList = ref([])
const selectedTtsId = ref(null)
const currentProviderType = ref('volcano')
const cloneList = ref([])

const aliyunPage = ref(1)
const aliyunPageSize = ref(10)
const aliyunTotal = ref(0)

const createDialogVisible = ref(false)
const createForm = ref({ 
  name: '', speaker_id: '', model_type: 1, language: 0, description: '',
  target_model: 'cosyvoice-v3-plus', prefix: '', url: '',
  language_hints: [], max_prompt_audio_length: 10, enable_preprocess: false
})

const uploadDialogVisible = ref(false)
const currentClone = ref({})
const uploadForm = ref({ reference_path: '', text: '', enable_denoise: true })

const detailDialogVisible = ref(false)
const currentDetail = ref(null)

const modelTypeMap = { 1: 'ICL 1.0', 2: 'DiT 标准版', 3: 'DiT 还原版', 4: 'ICL 2.0' }
const statusMap = { 0: '待上传', 1: '训练中', 2: '成功', 3: '失败', 4: '已激活' }
const statusTagMap = { 0: 'info', 1: 'warning', 2: 'success', 3: 'danger', 4: 'success' }
const modelTypeTagMap = { 1: '', 2: 'success', 3: 'warning', 4: 'danger' }

const getModelTypeName = (type) => modelTypeMap[type] || '未知'
const getStatusName = (status) => statusMap[status] || '未知'
const getStatusTag = (status) => statusTagMap[status] || 'info'
const getModelTypeTag = (type) => modelTypeTagMap[type] || 'info'

// 根据当前选择的模型动态计算语种选项
const currentLanguageOptions = computed(() => {
  return MODEL_LANGUAGE_MAP[createForm.value.target_model] || MODEL_LANGUAGE_MAP['cosyvoice-v3-plus']
})

// 模型切换时清空不支持的语种
const onTargetModelChange = () => {
  const allowedValues = currentLanguageOptions.value.map(l => l.value)
  createForm.value.language_hints = createForm.value.language_hints.filter(h => allowedValues.includes(h))
}

const loadTtsProviders = async () => {
  const allTts = await fetchTTSProviders()
  volcanoTtsList.value = allTts.filter(t => t.provider_type === 'volcano')
  aliyunTtsList.value = allTts.filter(t => t.provider_type === 'aliyun')
}

const loadClones = async () => {
  if (!selectedTtsId.value) return
  
  if (currentProviderType.value === 'aliyun') {
    const res = await queryAliyunVoiceList(selectedTtsId.value, aliyunPage.value - 1, aliyunPageSize.value)
    if (res.code === 200 && res.data) {
      cloneList.value = res.data.voices || []
      aliyunTotal.value = res.data.page_count || 0
    } else {
      cloneList.value = []
      aliyunTotal.value = 0
    }
  } else {
    const res = await fetchVoiceClones(selectedTtsId.value)
    cloneList.value = res.data || []
  }
}

const onTtsChange = () => {
  const [type, id] = selectedTtsId.value.split('-')
  currentProviderType.value = type
  selectedTtsId.value = parseInt(id)
  aliyunPage.value = 1
  loadClones()
}

const handlePageChange = (page) => {
  aliyunPage.value = page
  loadClones()
}

const refreshList = () => {
  aliyunPage.value = 1
  loadClones()
}

const handleSyncAll = async () => {
  try {
    const res = await syncAliyunVoices(selectedTtsId.value)
    if (res.code === 200) {
      ElMessage.success(`同步成功，共同步了 ${res.data} 个音色`)
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('同步失败')
  }
}

const handleSyncSingle = async (row) => {
  try {
    const res = await syncAliyunVoiceSingle(selectedTtsId.value, row.voice_id)
    if (res.code === 200) {
      ElMessage.success(`音色 "${row.voice_id}" 同步成功`)
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('同步失败')
  }
}

const openCreateDialog = () => {
  if (currentProviderType.value === 'aliyun') {
    createForm.value = {
      name: '', speaker_id: '', model_type: 1, language: 0, description: '',
      target_model: 'cosyvoice-v3-plus', prefix: '', url: '',
      language_hints: [], max_prompt_audio_length: 10, enable_preprocess: false
    }
  } else {
    createForm.value = {
      name: '', speaker_id: '', model_type: 1, language: 0, description: '',
      target_model: 'cosyvoice-v3-plus', prefix: '', url: '',
      language_hints: [], max_prompt_audio_length: 10, enable_preprocess: false
    }
  }
  createDialogVisible.value = true
}

const submitCreate = async () => {
  if (currentProviderType.value === 'aliyun') {
    if (!createForm.value.prefix || !createForm.value.url) {
      ElMessage.error('请填写必填项（目标模型、音色前缀、音频URL）')
      return
    }
    try {
      const data = {
        tts_provider_id: selectedTtsId.value,
        target_model: createForm.value.target_model,
        prefix: createForm.value.prefix,
        url: createForm.value.url,
        language_hints: createForm.value.language_hints?.length ? createForm.value.language_hints : null,
        max_prompt_audio_length: createForm.value.max_prompt_audio_length,
        enable_preprocess: createForm.value.enable_preprocess
      }
      await createAliyunVoice(data)
      ElMessage.success('创建成功')
      createDialogVisible.value = false
      await loadClones()
    } catch (e) {
      console.error(e)
      ElMessage.error('创建失败')
    }
  } else {
    if (!createForm.value.name || !createForm.value.speaker_id) {
      ElMessage.error('请填写必填项')
      return
    }
    try {
      await createVoiceClone({
        ...createForm.value,
        tts_provider_id: selectedTtsId.value
      })
      ElMessage.success('创建成功')
      createDialogVisible.value = false
      await loadClones()
    } catch (e) {
      ElMessage.error('创建失败')
    }
  }
}

const viewDetail = async (row) => {
  try {
    const res = await getAliyunVoiceDetail(selectedTtsId.value, row.voice_id)
    if (res.code === 200) {
      currentDetail.value = res.data
      detailDialogVisible.value = true
    } else {
      ElMessage.error('获取详情失败')
    }
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

const openUploadDialog = (row) => {
  currentClone.value = row
  uploadForm.value = { reference_path: row.reference_path || '', text: '', enable_denoise: true }
  uploadDialogVisible.value = true
}

const submitUpload = async () => {
  if (!uploadForm.value.reference_path) {
    ElMessage.error('请填写音频文件路径')
    return
  }
  try {
    await uploadAudio({
      clone_id: currentClone.value.id,
      reference_path: uploadForm.value.reference_path,
      text: uploadForm.value.text || undefined,
      enable_denoise: uploadForm.value.enable_denoise,
    })
    ElMessage.success('音频上传成功，训练中')
    uploadDialogVisible.value = false
    await loadClones()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.message || e.message))
  }
}

const refreshStatus = async (row) => {
  try {
    await queryStatus(row.id)
    ElMessage.success('状态已更新')
    await loadClones()
  } catch (e) {
    ElMessage.error('查询失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确认删除该声音复刻记录？', '提示', { type: 'warning' })
    
    if (currentProviderType.value === 'aliyun') {
      await deleteAliyunVoice(selectedTtsId.value, row.voice_id)
    } else {
      await deleteVoiceClone(row.id)
    }
    ElMessage.success('已删除')
    await loadClones()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(async () => {
  await loadTtsProviders()
})
</script>

<style scoped>
.toolbar { margin-bottom: 12px; display: flex; align-items: center; }
</style>
