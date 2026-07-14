<template>
  <div>
    <div class="page-header">
      <h2>音色管理</h2>
      <div class="actions">
        <el-select v-model="selectedTTS" placeholder="选择 TTS 引擎" class="tts-select" @change="onTTSChange">
          <el-option v-for="t in ttsProviders" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-button v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" type="primary" :disabled="!selectedTTS" @click="openDialog()">新增音色</el-button>
        <el-button v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" type="success" plain :disabled="!selectedTTS || selectedCount === 0" @click="handleExportSelected">导出音色库（选中）</el-button>
        <el-popconfirm
          v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'"
          title="确认删除选中的音色？"
          confirm-button-text="确定"
          cancel-button-text="取消"
          @confirm="handleBatchDelete"
        >
          <template #reference>
            <el-button type="danger" plain :disabled="!selectedTTS || selectedCount === 0">批量删除（选中）</el-button>
          </template>
        </el-popconfirm>
        <el-button v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" type="warning" :disabled="!selectedTTS" @click="handleImport">导入音色库</el-button>
        <!-- 阿里云专属按钮 -->
        <el-button v-if="currentProviderType === 'aliyun'" type="primary" :disabled="!selectedTTS" @click="openAliyunCreateDialog">创建音色（声音复刻）</el-button>
        <el-button v-if="currentProviderType === 'aliyun'" type="success" plain :disabled="!selectedTTS" @click="handleSyncAllAliyunVoices">同步全部到本地</el-button>
        <!-- 火山引擎声音复刻按钮 -->
        <el-button v-if="currentProviderType === 'volcano'" type="primary" :disabled="!selectedTTS" @click="openVolcanoCloneDialog">新增声音复刻</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-tag v-if="currentProviderType === 'volcano'" type="warning" effect="plain">火山引擎音色库</el-tag>
      <template v-else-if="currentProviderType === 'aliyun'">
        <el-tag type="primary" effect="plain">阿里云音色库（云端）</el-tag>
        <el-input v-model="aliyunPrefix" placeholder="按名称前缀搜索" clearable class="filter-search" @keyup.enter="handleAliyunSearch" />
        <el-button plain @click="handleAliyunSearch">搜索</el-button>
        <el-button plain :disabled="!aliyunPrefix" @click="handleAliyunResetSearch">重置</el-button>
      </template>
      <template v-else>
        <el-select
          ref="filterSelectRef"
          v-model="filterTags"
          multiple
          filterable
          clearable
          collapse-tags
          collapse-tags-tooltip
          placeholder="标签筛选"
          class="filter-tags"
          @change="handleFilterTagChange"
        >
          <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
        </el-select>
        <el-input v-model="searchName" placeholder="按名称搜索" clearable class="filter-search" />
        <el-button plain :disabled="!searchName && !filterTags.length" @click="resetFilters">重置筛选</el-button>
        <div class="filter-result">共 {{ filteredVoices.length }} 条</div>
      </template>
    </div>

    <el-table
      :data="currentProviderType === 'volcano' || currentProviderType === 'aliyun' ? voices : filteredVoices"
      ref="voiceTableRef"
      border
      stripe
      highlight-current-row
      class="voice-table"
      :header-cell-style="headerCellStyle"
      :cell-style="cellStyle"
      :row-key="(row, index) => {
        if (currentProviderType === 'volcano') return row.SpeakerID ?? `fb-${index}`;
        if (currentProviderType === 'aliyun') return row.voice_id || row.VoiceId || row.voiceId || row.id || `fb-${index}`;
        return row.id ?? `fb-${index}`;
      }"
      @selection-change="handleSelectionChange"
    >
      <el-table-column v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" type="selection" width="48" align="center" />
      <el-table-column label="#" width="80" align="center">
        <template #default="{ $index }">
          <template v-if="currentProviderType === 'volcano'">{{ (volcanoPage - 1) * volcanoPageSize + $index + 1 }}</template>
          <template v-else-if="currentProviderType === 'aliyun'">{{ aliyunPage * aliyunPageSize + $index + 1 }}</template>
          <template v-else>{{ $index + 1 }}</template>
        </template>
      </el-table-column>

      <el-table-column label="来源" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="currentProviderType === 'index_tts'" type="success" effect="plain">本地</el-tag>
          <el-tag v-else-if="currentProviderType === 'volcano'" type="primary" effect="plain">火山引擎</el-tag>
          <el-tag v-else-if="currentProviderType === 'aliyun'" type="primary" effect="plain">阿里云</el-tag>
          <el-tag v-else type="info" effect="plain">{{ currentProviderType || '未知' }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="名称" min-width="180">
        <template #default="{ row }">
          <template v-if="currentProviderType === 'volcano'">{{ row.SpeakerID }}</template>
          <template v-else-if="currentProviderType === 'aliyun'">{{ row.name || row.voice_id || row.VoiceId || row.voiceId }}</template>
          <template v-else>{{ row.name }}</template>
        </template>
      </el-table-column>

      <el-table-column label="播放" width="160" align="center">
        <template #default="{ row }">
          <template v-if="currentProviderType === 'volcano'">
            <span class="no-audio-tip">—</span>
          </template>
          <template v-else-if="currentProviderType === 'aliyun'">
            <el-button
              v-if="row.demo_url || row.DemoUrl || row.demo_audio_url"
              size="small"
              type="primary"
              @click="playAliyunDemo(row)"
            >
              <el-icon style="margin-right:4px;"><Headset /></el-icon>
              试听
            </el-button>
            <span v-else class="no-audio-tip">—</span>
          </template>
          <template v-else>
            <el-button
              v-if="row.reference_path"
              size="small"
              type="primary"
              @click="togglePlay(row.reference_path)"
            >
              <el-icon style="margin-right:4px;"><Headset /></el-icon>
              {{ isPlaying && currentPath === row.reference_path ? '暂停' : '播放' }}
            </el-button>
            <span v-else class="no-audio-tip">—</span>
          </template>
        </template>
      </el-table-column>

      <!-- 描述改为 tag 展示 -->
      <el-table-column v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" prop="description" label="标签" min-width="220">
        <template #default="{ row }">
          <div class="tags-wrap">
            <el-tag
              v-for="(tag, index) in (row.description ? row.description.split(',') : [])"
              :key="index"
              type="info"
              effect="plain"
              style="margin-right: 6px;"
            >
              {{ tag }}
            </el-tag>
            <span v-if="!row.description">—</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" label="参考音频/路径" min-width="200" align="center">
        <template #default="{ row }">
          <el-tooltip :content="row.reference_path ? row.reference_path : '未设置参考音频'" placement="top">
            <span class="path-ellipsis">{{ row.reference_path || '（未设置）' }}</span>
          </el-tooltip>
        </template>
      </el-table-column>

      <el-table-column v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" label="创建时间" width="180">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="currentProviderType !== 'volcano' && currentProviderType !== 'aliyun'" label="更新时间" width="180">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>

      <template v-if="currentProviderType === 'volcano'">
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="stateTagType(row.State)" effect="plain">{{ stateLabel(row.State) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="Alias" label="别名" min-width="140">
          <template #default="{ row }">{{ row.Alias || '—' }}</template>
        </el-table-column>
        <el-table-column prop="Version" label="版本" width="80" align="center" />
        <el-table-column label="到期时间" width="180" align="center">
          <template #default="{ row }">{{ row.ExpireTime ? formatTimestamp(row.ExpireTime) : '—' }}</template>
        </el-table-column>
        <el-table-column label="剩余训练" width="100" align="center">
          <template #default="{ row }">{{ row.AvailableTrainingTimes ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="Demo" width="100" align="center">
          <template #default="{ row }">
            <el-button v-if="row.DemoAudio" size="small" type="primary" plain @click="playDemoAudio(row.DemoAudio)">试听</el-button>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="复刻状态" width="110" align="center">
          <template #default="{ row }">
            <template v-if="row._clone">
              <el-tag :type="cloneStatusTagType(row._clone.status)" size="small">{{ cloneStatusName(row._clone.status) }}</el-tag>
            </template>
            <span v-else class="no-audio-tip">—</span>
          </template>
        </el-table-column>
      </template>

      <!-- 阿里云专属列 -->
      <template v-if="currentProviderType === 'aliyun'">
        <el-table-column label="Voice ID" min-width="180">
          <template #default="{ row }">{{ row.voice_id || row.VoiceId || row.voiceId || '—' }}</template>
        </el-table-column>
        <el-table-column label="模型" min-width="160">
          <template #default="{ row }">{{ row.model || row.target_model || '—' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ row.gmt_create || row.created_time || formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="Demo" width="100" align="center">
          <template #default="{ row }">
            <el-button v-if="row.demo_url || row.DemoUrl || row.demo_audio_url" size="small" type="primary" plain @click="playAliyunDemo(row)">试听</el-button>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </template>

      <el-table-column label="操作" :width="currentProviderType === 'volcano' ? 320 : currentProviderType === 'aliyun' ? 340 : 320" fixed="right" align="center">
        <template #default="{ row }">
          <div class="flex justify-center gap-2">
            <template v-if="currentProviderType === 'volcano'">
              <el-button type="success" size="small" plain @click="handleSyncSingleVoice(row)">同步到本地</el-button>
              <template v-if="row._clone">
                <el-button size="small" plain @click="openVolcanoUploadDialog(row._clone)" :disabled="row._clone.status === 1">上传训练</el-button>
                <el-button size="small" type="warning" plain @click="handleRefreshCloneStatus(row._clone)" :disabled="row._clone.status !== 1">刷新状态</el-button>
                <el-popconfirm
                  title="确认删除该复刻记录？"
                  confirm-button-text="确定"
                  cancel-button-text="取消"
                  @confirm="handleDeleteClone(row._clone)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </template>
            <template v-else-if="currentProviderType === 'aliyun'">
              <el-button type="success" size="small" plain @click="handleSyncSingleAliyunVoice(row)">同步到本地</el-button>
              <el-button type="primary" size="small" plain @click="openAliyunUpdateDialog(row)">更新</el-button>
              <el-popconfirm
                title="确认删除该阿里云音色？（将同时删除本地记录）"
                confirm-button-text="确定"
                cancel-button-text="取消"
                @confirm="handleDeleteAliyunVoice(row)"
              >
                <template #reference>
                  <el-button type="danger" size="small" plain>删除</el-button>
                </template>
              </el-popconfirm>
            </template>
            <template v-else>
              <el-button type="primary" size="small" plain @click="openDialog(row)" :disabled="currentProviderType === 'aliyun'">编辑</el-button>
              <el-button type="success" size="small" plain @click="openCopyDialog(row)" :disabled="currentProviderType === 'aliyun'">复制</el-button>
              <el-button type="warning" size="small" plain :disabled="!row.reference_path || currentProviderType === 'aliyun'" @click="openAudioEditor(row)">音频编辑</el-button>
              <el-popconfirm
                v-if="currentProviderType !== 'aliyun'"
                title="确认删除该音色？"
                confirm-button-text="确定"
                cancel-button-text="取消"
                @confirm="handleDelete(row.id)"
              >
                <template #reference>
                  <el-button type="danger" size="small" plain>删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </div>
        </template>
      </el-table-column>

    </el-table>

    <div v-if="currentProviderType === 'volcano'" class="pagination-wrap">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="volcanoTotal"
        :current-page="volcanoPage"
        :page-size="volcanoPageSize"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="handleVolcanoPageChange"
        @size-change="handleVolcanoSizeChange"
      />
    </div>

    <div v-if="currentProviderType === 'aliyun'" class="pagination-wrap">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="aliyunTotal"
        :current-page="aliyunPage + 1"
        :page-size="aliyunPageSize"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="handleAliyunPageChange"
        @size-change="handleAliyunSizeChange"
      />
    </div>

    <!-- 弹窗：新增/编辑 -->
    <el-dialog :title="form.id ? '编辑音色' : '新增音色'" v-model="dialogVisible" width="720px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入音色名称" />
        </el-form-item>

        <!-- 描述改为标签输入 -->
        <el-form-item label="标签" class="tag-item">
  <div class="tag-hint">可直接选择下方标签，也可以输入自定义标签后回车添加</div>
  <el-select
    ref="tagSelectRef"
    v-model="form.tags"
    multiple
    filterable
    allow-create
    default-first-option
    placeholder="输入或选择标签（回车添加）"
    style="width: 100%;"
    @change="handleTagChange"
  >
    <el-option
      v-for="opt in defaultTags"
      :key="opt"
      :label="opt"
      :value="opt"
    />
  </el-select>
</el-form-item>



        <el-form-item label="参考音频">
          <div class="pick-line">
            <el-input v-model="form.reference_path" placeholder="请选择本地音频文件" readonly style="width:420px" />
            <el-button @click="pickLocalAudioForBase" style="margin-left:8px">选择文件</el-button>
            <el-button v-if="form.reference_path" type="danger" link @click="clearReferencePath">清除</el-button>
          </div>

          <div class="preview" v-if="form.reference_path">
            <el-alert title="已选择本地音频文件" type="success" :closable="false" show-icon class="mb8" />
            <div class="path-text">{{ form.reference_path }}</div>
            <el-button type="primary" size="small" @click="togglePlay(form.reference_path)">
              {{ isPlaying && currentPath === form.reference_path ? '暂停' : '播放' }}
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：音频编辑 -->
    <el-dialog title="音频编辑" v-model="audioEditorVisible" width="900px" :close-on-click-modal="false">
      <div class="audio-editor-info" v-if="editingVoice">
        <span class="audio-editor-label">音色名称：</span>
        <span class="audio-editor-value">{{ editingVoice.name }}</span>
      </div>
      <div class="wave-editor-wrap" v-if="editingVoice?.reference_path && waveEditorKey">
        <WaveCellPro
          :key="waveEditorKey"
          :src="editingVoice.reference_path"
          :speed="1.0"
          :volume2x="1.0"
          @confirm="handleWaveConfirm"
          @ready="handleWaveReady"
        />
      </div>
      <template #footer>
        <el-button @click="audioEditorVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：导入音色库 -->
    <el-dialog title="导入音色库" v-model="importDialogVisible" width="600px">
      <el-form :model="importForm" label-width="120px">
        <el-form-item label="音色库文件">
          <div class="pick-line">
            <el-input v-model="importForm.zipPath" placeholder="请选择音色库zip文件" readonly style="flex:1" />
            <el-button @click="pickImportZip" style="margin-left:8px">选择文件</el-button>
          </div>
        </el-form-item>
        <el-form-item label="音色保存目录">
          <div class="pick-line">
            <el-input v-model="importForm.targetDir" placeholder="音色文件保存目录" style="flex:1" />
            <el-button @click="pickImportDir" style="margin-left:8px">选择目录</el-button>
          </div>
          <div class="form-hint">导入的音色文件将保存到此目录</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!importForm.zipPath || !importForm.targetDir" @click="confirmImport">确认导入</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：复制音色 -->
    <el-dialog title="复制音色" v-model="copyDialogVisible" width="600px">
      <el-form :model="copyForm" :rules="copyRules" ref="copyFormRef" label-width="120px">
        <el-form-item label="原音色名称">
          <el-input :value="copyForm.sourceName" disabled />
        </el-form-item>
        <el-form-item label="新音色名称" prop="newName">
          <el-input v-model="copyForm.newName" placeholder="请输入新音色名称" />
        </el-form-item>
        <el-form-item label="保存目录">
          <div class="pick-line">
            <el-input v-model="copyForm.targetDir" placeholder="留空则保存到原音色同目录" style="flex:1" />
            <el-button @click="pickCopyTargetDir" style="margin-left:8px">选择目录</el-button>
          </div>
          <div class="form-hint">留空则将新音色文件保存到原音色所在目录</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!copyForm.newName" @click="confirmCopy">确认复制</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：阿里云创建音色（声音复刻） -->
    <el-dialog title="创建阿里云音色（声音复刻）" v-model="aliyunCreateDialogVisible" width="650px">
      <el-form :model="aliyunCreateForm" :rules="aliyunCreateRules" ref="aliyunCreateFormRef" label-width="140px">
        <el-form-item label="合成模型" prop="target_model">
          <el-select v-model="aliyunCreateForm.target_model" placeholder="选择模型" style="width: 100%">
            <el-option v-for="m in aliyunModelOptions" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
          <div class="form-hint">必须与后续语音合成使用的模型一致，否则合成会失败</div>
        </el-form-item>
        <el-form-item label="音色前缀" prop="prefix">
          <el-input v-model="aliyunCreateForm.prefix" placeholder="仅允许数字和英文字母，不超过10个字符" maxlength="10" />
        </el-form-item>
        <el-form-item label="音频 URL" prop="url">
          <el-input v-model="aliyunCreateForm.url" placeholder="公网可访问的音频文件 URL" />
        </el-form-item>
        <el-form-item label="语种提示">
          <el-select v-model="aliyunCreateForm.language_hints" multiple filterable placeholder="选择语种" style="width: 100%">
            <el-option v-for="lang in aliyunLangOptions" :key="lang.value" :label="lang.label" :value="lang.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="音频最大时长">
          <el-input-number v-model="aliyunCreateForm.max_prompt_audio_length" :min="3" :max="30" :step="0.5" :precision="1" placeholder="3.0 ~ 30.0 秒" style="width: 200px" />
          <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px;">秒（仅 v3.5/v3-flash 支持）</span>
        </el-form-item>
        <el-form-item label="音频预处理">
          <el-switch v-model="aliyunCreateForm.enable_preprocess" active-text="开启" inactive-text="关闭" />
          <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px;">降噪、音频增强、音量规整（仅 v3.5/v3-flash 支持）</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aliyunCreateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAliyunCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：阿里云更新音色 -->
    <el-dialog title="更新阿里云音色" v-model="aliyunUpdateDialogVisible" width="650px">
      <el-form :model="aliyunUpdateForm" :rules="aliyunUpdateRules" ref="aliyunUpdateFormRef" label-width="140px">
        <el-form-item label="音色 ID">
          <el-input :value="aliyunUpdateForm.voice_id" disabled />
        </el-form-item>
        <el-form-item label="新音频 URL" prop="url">
          <el-input v-model="aliyunUpdateForm.url" placeholder="公网可访问的音频文件 URL" />
        </el-form-item>
        <el-form-item label="语种提示">
          <el-select v-model="aliyunUpdateForm.language_hints" multiple filterable placeholder="选择语种" style="width: 100%">
            <el-option v-for="lang in aliyunLangOptions" :key="lang.value" :label="lang.label" :value="lang.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="音频最大时长">
          <el-input-number v-model="aliyunUpdateForm.max_prompt_audio_length" :min="3" :max="30" :step="0.5" :precision="1" style="width: 200px" />
          <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px;">秒</span>
        </el-form-item>
        <el-form-item label="音频预处理">
          <el-switch v-model="aliyunUpdateForm.enable_preprocess" active-text="开启" inactive-text="关闭" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aliyunUpdateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAliyunUpdate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：火山引擎声音复刻 -->
    <el-dialog title="新增火山引擎声音复刻" v-model="volcanoCloneDialogVisible" width="600px">
      <el-form :model="volcanoCloneForm" :rules="volcanoCloneRules" ref="volcanoCloneFormRef" label-width="120px">
        <el-form-item label="音色名称" prop="name">
          <el-input v-model="volcanoCloneForm.name" placeholder="如：我的声音" />
        </el-form-item>
        <el-form-item label="Speaker ID" prop="speaker_id">
          <el-input v-model="volcanoCloneForm.speaker_id" placeholder="S_开头，从控制台获取" />
        </el-form-item>
        <el-form-item label="模型类型" prop="model_type">
          <el-select v-model="volcanoCloneForm.model_type" style="width: 100%">
            <el-option label="ICL 1.0" :value="1" />
            <el-option label="DiT 标准版" :value="2" />
            <el-option label="DiT 还原版" :value="3" />
            <el-option label="ICL 2.0" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="语种" prop="language">
          <el-select v-model="volcanoCloneForm.language" style="width: 100%">
            <el-option label="中文" :value="0" />
            <el-option label="英文" :value="1" />
            <el-option label="日语" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="volcanoCloneForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="volcanoCloneDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitVolcanoClone">确定</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：火山引擎上传训练 -->
    <el-dialog :title="'上传训练 - ' + volcanoUploadClone.name" v-model="volcanoUploadDialogVisible" width="500px">
      <el-form :model="volcanoUploadForm" label-width="120px">
        <el-form-item label="音频文件">
          <div class="pick-line">
            <el-input v-model="volcanoUploadForm.reference_path" placeholder="请选择本地音频文件" readonly style="flex:1" />
            <el-button @click="pickVolcanoAudioFile">选择文件</el-button>
          </div>
        </el-form-item>
        <el-form-item label="参考文本">
          <el-input v-model="volcanoUploadForm.text" type="textarea" :rows="2" placeholder="可选，音频朗读的内容" />
        </el-form-item>
        <el-form-item label="降噪">
          <el-switch v-model="volcanoUploadForm.enable_denoise" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="volcanoUploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitVolcanoUpload">开始训练</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import { Headset } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { createVoice, fetchVoicesByTTS, updateVoice, deleteVoice, exportVoices, importVoices, processVoiceAudio, copyVoice } from '../api/voice'
import { fetchTTSProviders } from '../api/provider'
import { queryVolcanoVoiceList, syncVolcanoVoiceSingle, orderVolcanoVoices, renewVolcanoVoices } from '../api/volcano_voice'
import { queryAliyunVoiceManagerList, syncAliyunVoiceManagerAll, syncAliyunVoiceManagerSingle, createAliyunVoiceManager, updateAliyunVoiceManager, deleteAliyunVoiceManager } from '../api/aliyun_voice_manager'
import { fetchVoiceClones, createVoiceClone, deleteVoiceClone, uploadAudio, queryStatus } from '../api/voice_clone'
import WaveCellPro from '../components/WaveCellPro.vue'


const defaultTags = ref([
  '男',
  '女',
  '小孩',
  '青年',
  '中年',
  '老年'
])

// @ts-ignore - 由 preload 暴露
const native = window.native

const ttsProviders = ref([])
const selectedTTS = ref(null)
const currentProviderType = ref(null)
const voices = ref([])
const voiceTableRef = ref(null)
const selectedRows = ref([])
const selectedIds = computed(() => (selectedRows.value || []).map(v => v?.id ?? v?.SpeakerID).filter(v => v !== null && v !== undefined))
const selectedCount = computed(() => selectedIds.value.length)

const volcanoPage = ref(1)
const volcanoPageSize = ref(20)
const volcanoTotal = ref(0)

// ====== 阿里云音色分页和搜索 ======
const aliyunPage = ref(0)
const aliyunPageSize = ref(20)
const aliyunTotal = ref(0)
const aliyunPrefix = ref('')

const filterTags = ref([])
const searchName = ref('')
const filterSelectRef = ref(null)

const allTags = computed(() => {
  const set = new Set()
  defaultTags.value.forEach(t => t && set.add(t))
  voices.value.forEach(v => {
    const tags = v.description ? v.description.split(',') : []
    tags.map(t => t.trim()).filter(Boolean).forEach(t => set.add(t))
  })
  return Array.from(set)
})

const filteredVoices = computed(() => {
  const name = searchName.value.trim()
  const nameLower = name.toLowerCase()
  return voices.value.filter(v => {
    const voiceName = (v.name || '').toString()
    const matchName = !name || voiceName.toLowerCase().includes(nameLower)
    if (!filterTags.value.length) return matchName
    const tags = v.description ? v.description.split(',').map(t => t.trim()).filter(Boolean) : []
    const matchTags = filterTags.value.every(ft => tags.includes(ft))
    return matchName && matchTags
  })
})

function handleSelectionChange(rows) {
  selectedRows.value = rows || []
}

function formatDateTime(value) {
  if (!value) return '—'
  const d = dayjs(value)
  if (!d.isValid()) return String(value)
  return d.format('YYYY-MM-DD HH:mm:ss')
}

async function clearTableSelection() {
  await nextTick()
  voiceTableRef.value?.clearSelection?.()
  selectedRows.value = []
}

// ====== 音频播放控制 ======
const audioPlayer = new Audio()
const isPlaying = ref(false)
const currentPath = ref(null)

function togglePlay(absPath) {
  if (!absPath) return
  const url = toFileUrl(absPath)
  if (!url) {
    ElMessage.error('无法播放该音频文件')
    return
  }

  if (currentPath.value === absPath) {
    if (isPlaying.value) {
      audioPlayer.pause()
    } else {
      audioPlayer.play().catch(() => ElMessage.error('无法播放该音频文件'))
    }
    return
  }

  audioPlayer.pause()
  audioPlayer.src = url
  audioPlayer.currentTime = 0
  currentPath.value = absPath
  audioPlayer.play().catch(() => ElMessage.error('无法播放该音频文件'))
}

audioPlayer.addEventListener('play', () => { isPlaying.value = true })
audioPlayer.addEventListener('pause', () => { isPlaying.value = false })
audioPlayer.addEventListener('ended', () => {
  isPlaying.value = false
  currentPath.value = null
})

const dialogVisible = ref(false)
watch(dialogVisible, v => { 
  if (!v) {
    audioPlayer.pause()
  }
})

// ====== 独立音频编辑弹窗 ======
const audioEditorVisible = ref(false)
const editingVoice = ref(null)

watch(audioEditorVisible, v => {
  if (!v) {
    audioPlayer.pause()
    waveEditorKey.value = null
    editingVoice.value = null
  }
})

function openAudioEditor(row) {
  if (!row.reference_path) {
    ElMessage.warning('该音色没有参考音频')
    return
  }
  audioPlayer.pause()
  editingVoice.value = row
  waveEditorKey.value = Date.now()
  audioEditorVisible.value = true
}

// 表单
const formRef = ref(null)
const form = ref({
  id: null,
  name: '',
  tags: [],
  reference_path: '',
  tts_provider_id: null
})

const rules = {
  name: [{ required: true, message: '请输入音色名称', trigger: 'blur' }]
}

// 表格样式
const headerCellStyle = () => ({
  background: 'var(--el-fill-color-light)',
  color: 'var(--el-text-color-primary)',
  fontWeight: 600
})
const cellStyle = () => ({ padding: '10px 12px' })

const loadTTS = async () => {
  const providers = await fetchTTSProviders()
  ttsProviders.value = providers
  const def = providers.find(t => t.id === 1) || providers[0]
  if (def) {
    selectedTTS.value = def.id
    const selectedProvider = providers.find(t => t.id === def.id)
    currentProviderType.value = selectedProvider?.provider_type || null
    await loadVoices()
  }
}

const loadVoices = async () => {
  if (!selectedTTS.value) return

  if (currentProviderType.value === 'volcano') {
    try {
      const [res, cloneRes] = await Promise.all([
        queryVolcanoVoiceList(selectedTTS.value, {
          pageNumber: volcanoPage.value,
          pageSize: volcanoPageSize.value
        }),
        fetchVoiceClones(selectedTTS.value).catch(() => ({ data: [] }))
      ])
      if (res.code === 200 && res.data) {
        const result = res.data.Result || res.data
        const cloudVoices = result.Statuses || []
        const clones = cloneRes.data || []
        const cloneMap = {}
        clones.forEach(c => { if (c.speaker_id) cloneMap[c.speaker_id] = c })
        voices.value = cloudVoices.map(v => ({
          ...v,
          _clone: cloneMap[v.SpeakerID] || null
        }))
        volcanoTotal.value = result.TotalCount || 0
      } else {
        voices.value = []
        volcanoTotal.value = 0
      }
    } catch (e) {
      console.error(e)
      voices.value = []
      volcanoTotal.value = 0
      ElMessage.error('加载火山引擎音色列表失败')
    }
  } else if (currentProviderType.value === 'aliyun') {
    try {
      const res = await queryAliyunVoiceManagerList(
        selectedTTS.value,
        aliyunPage.value,
        aliyunPageSize.value,
        aliyunPrefix.value || undefined
      )
      if (res.code === 200 && res.data) {
        voices.value = res.data.voices || []
        aliyunTotal.value = res.data.total || 0
      } else {
        voices.value = []
        aliyunTotal.value = 0
      }
    } catch (e) {
      console.error(e)
      voices.value = []
      aliyunTotal.value = 0
      ElMessage.error('加载阿里云音色列表失败')
    }
  } else {
    const list = await fetchVoicesByTTS(selectedTTS.value)
    voices.value = list || []
  }
  await clearTableSelection()
}

async function handleVolcanoPageChange(page) {
  volcanoPage.value = page
  await loadVoices()
}

async function handleVolcanoSizeChange(size) {
  volcanoPageSize.value = size
  volcanoPage.value = 1
  await loadVoices()
}

// ====== 阿里云音色分页和搜索 ======
async function handleAliyunPageChange(page) {
  aliyunPage.value = page - 1  // 阿里云 API 使用 0-based 页码
  await loadVoices()
}

async function handleAliyunSizeChange(size) {
  aliyunPageSize.value = size
  aliyunPage.value = 0
  await loadVoices()
}

async function handleAliyunSearch() {
  aliyunPage.value = 0
  await loadVoices()
}

async function handleAliyunResetSearch() {
  aliyunPrefix.value = ''
  aliyunPage.value = 0
  await loadVoices()
}

// ====== 阿里云音色同步 ======
async function handleSyncAllAliyunVoices() {
  try {
    const loading = ElLoading.service({
      lock: true,
      text: '正在同步阿里云音色...',
      background: 'rgba(0, 0, 0, 0.4)'
    })
    const res = await syncAliyunVoiceManagerAll(selectedTTS.value)
    loading.close()
    if (res.code === 200) {
      ElMessage.success(res.message || '同步成功')
      await loadVoices()
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('同步失败')
  }
}

async function handleSyncSingleAliyunVoice(row) {
  const voiceId = row.voice_id || row.VoiceId || row.voiceId
  if (!voiceId) {
    ElMessage.warning('无法获取音色 ID')
    return
  }
  try {
    const res = await syncAliyunVoiceManagerSingle(selectedTTS.value, voiceId)
    if (res.code === 200) {
      ElMessage.success(res.message || '同步成功')
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('同步失败')
  }
}

// ====== 阿里云音色删除 ======
async function handleDeleteAliyunVoice(row) {
  const voiceId = row.voice_id || row.VoiceId || row.voiceId
  if (!voiceId) {
    ElMessage.warning('无法获取音色 ID')
    return
  }
  try {
    const res = await deleteAliyunVoiceManager({
      tts_provider_id: selectedTTS.value,
      voice_id: voiceId,
      delete_local: true
    })
    if (res.code === 200) {
      ElMessage.success('删除成功')
      await loadVoices()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

// ====== 阿里云音色试听 ======
function playAliyunDemo(row) {
  const url = row.demo_url || row.DemoUrl || row.demo_audio_url
  if (!url) {
    ElMessage.warning('该音色没有 Demo 音频')
    return
  }
  audioPlayer.pause()
  audioPlayer.src = url
  audioPlayer.currentTime = 0
  currentPath.value = url
  audioPlayer.play().catch(() => ElMessage.error('无法播放 Demo 音频'))
}

// ====== 阿里云音色创建弹窗 ======
const aliyunCreateDialogVisible = ref(false)
const aliyunCreateFormRef = ref(null)
const aliyunCreateForm = ref({
  target_model: 'cosyvoice-v3-plus',
  prefix: '',
  url: '',
  language_hints: ['zh'],
  max_prompt_audio_length: null,
  enable_preprocess: true
})

const aliyunCreateRules = {
  target_model: [{ required: true, message: '请选择模型', trigger: 'change' }],
  prefix: [
    { required: true, message: '请输入音色前缀', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9]{1,10}$/, message: '仅允许数字和英文字母，不超过10个字符', trigger: 'blur' }
  ],
  url: [{ required: true, message: '请输入音频文件 URL', trigger: 'blur' }]
}

const aliyunModelOptions = [
  { label: 'cosyvoice-v3-plus', value: 'cosyvoice-v3-plus' },
  { label: 'cosyvoice-v3.5-plus', value: 'cosyvoice-v3.5-plus' },
  { label: 'cosyvoice-v3.5-flash', value: 'cosyvoice-v3.5-flash' },
  { label: 'cosyvoice-v3-flash', value: 'cosyvoice-v3-flash' },
]

const aliyunLangOptions = [
  { label: '中文', value: 'zh' },
  { label: '英文', value: 'en' },
  { label: '日语', value: 'ja' },
  { label: '韩语', value: 'ko' },
  { label: '法语', value: 'fr' },
  { label: '德语', value: 'de' },
  { label: '俄语', value: 'ru' },
  { label: '葡萄牙语', value: 'pt' },
  { label: '泰语', value: 'th' },
  { label: '印尼语', value: 'id' },
  { label: '越南语', value: 'vi' },
]

function openAliyunCreateDialog() {
  aliyunCreateForm.value = {
    target_model: 'cosyvoice-v3-plus',
    prefix: '',
    url: '',
    language_hints: ['zh'],
    max_prompt_audio_length: null,
    enable_preprocess: true
  }
  aliyunCreateDialogVisible.value = true
}

async function submitAliyunCreate() {
  aliyunCreateFormRef.value?.validate(async (valid) => {
    if (!valid) return
    try {
      const data = {
        tts_provider_id: selectedTTS.value,
        target_model: aliyunCreateForm.value.target_model,
        prefix: aliyunCreateForm.value.prefix,
        url: aliyunCreateForm.value.url,
      }
      if (aliyunCreateForm.value.language_hints && aliyunCreateForm.value.language_hints.length) {
        data.language_hints = aliyunCreateForm.value.language_hints
      }
      if (aliyunCreateForm.value.max_prompt_audio_length) {
        data.max_prompt_audio_length = aliyunCreateForm.value.max_prompt_audio_length
      }
      if (aliyunCreateForm.value.enable_preprocess !== null) {
        data.enable_preprocess = aliyunCreateForm.value.enable_preprocess
      }
      const res = await createAliyunVoiceManager(data)
      if (res.code === 200) {
        ElMessage.success(`创建成功，voice_id: ${res.data?.voice_id || ''}`)
        aliyunCreateDialogVisible.value = false
        await loadVoices()
      } else {
        ElMessage.error(res.message || '创建失败')
      }
    } catch (e) {
      console.error(e)
      ElMessage.error('创建失败')
    }
  })
}

// ====== 阿里云音色更新弹窗 ======
const aliyunUpdateDialogVisible = ref(false)
const aliyunUpdateFormRef = ref(null)
const aliyunUpdateForm = ref({
  voice_id: '',
  url: '',
  language_hints: ['zh'],
  max_prompt_audio_length: null,
  enable_preprocess: true
})

const aliyunUpdateRules = {
  url: [{ required: true, message: '请输入新的音频文件 URL', trigger: 'blur' }]
}

function openAliyunUpdateDialog(row) {
  const voiceId = row.voice_id || row.VoiceId || row.voiceId
  aliyunUpdateForm.value = {
    voice_id: voiceId,
    url: '',
    language_hints: ['zh'],
    max_prompt_audio_length: null,
    enable_preprocess: true
  }
  aliyunUpdateDialogVisible.value = true
}

async function submitAliyunUpdate() {
  aliyunUpdateFormRef.value?.validate(async (valid) => {
    if (!valid) return
    try {
      const data = {
        tts_provider_id: selectedTTS.value,
        voice_id: aliyunUpdateForm.value.voice_id,
        url: aliyunUpdateForm.value.url,
      }
      if (aliyunUpdateForm.value.language_hints && aliyunUpdateForm.value.language_hints.length) {
        data.language_hints = aliyunUpdateForm.value.language_hints
      }
      if (aliyunUpdateForm.value.max_prompt_audio_length) {
        data.max_prompt_audio_length = aliyunUpdateForm.value.max_prompt_audio_length
      }
      if (aliyunUpdateForm.value.enable_preprocess !== null) {
        data.enable_preprocess = aliyunUpdateForm.value.enable_preprocess
      }
      const res = await updateAliyunVoiceManager(data)
      if (res.code === 200) {
        ElMessage.success('更新成功')
        aliyunUpdateDialogVisible.value = false
        await loadVoices()
      } else {
        ElMessage.error(res.message || '更新失败')
      }
    } catch (e) {
      console.error(e)
      ElMessage.error('更新失败')
    }
  })
}

async function onTTSChange() {
  const selectedProvider = ttsProviders.value.find(t => t.id === selectedTTS.value)
  currentProviderType.value = selectedProvider?.provider_type || null
  volcanoPage.value = 1
  aliyunPage.value = 0
  aliyunPrefix.value = ''
  await loadVoices()
}

async function handleSyncSingleVoice(row) {
  try {
    const speakerId = row.SpeakerID
    const res = await syncVolcanoVoiceSingle(selectedTTS.value, speakerId)
    if (res.code === 200) {
      ElMessage.success(`音色 "${speakerId}" 同步成功`)
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('同步失败')
  }
}

function stateTagType(state) {
  const map = { Unknown: 'info', Training: '', Success: 'success', Active: 'success', Expired: 'danger', Reclaimed: 'info' }
  return map[state] || 'info'
}

function stateLabel(state) {
  const map = { Unknown: '未训练', Training: '训练中', Success: '训练成功', Active: '已激活', Expired: '已过期', Reclaimed: '已回收' }
  return map[state] || state || '未知'
}

function formatTimestamp(ts) {
  if (!ts) return '—'
  return dayjs(ts).format('YYYY-MM-DD HH:mm:ss')
}

function playDemoAudio(url) {
  if (!url) return
  audioPlayer.pause()
  audioPlayer.src = url
  audioPlayer.currentTime = 0
  currentPath.value = url
  audioPlayer.play().catch(() => ElMessage.error('无法播放Demo音频'))
}

function openDialog(row) {
  if (row) {
    form.value = {
      id: row.id ?? null,
      name: row.name,
      reference_path: row.reference_path || '',
      tts_provider_id: row.tts_provider_id || selectedTTS.value || 1,
      tags: row.description ? row.description.split(',') : []
    }
  } else {
    form.value = {
      id: null,
      name: '',
      reference_path: '',
      tts_provider_id: selectedTTS.value || 1,
      tags: []
    }
  }
  dialogVisible.value = true
}

async function pickLocalAudioForBase() {
  const p = await native?.pickAudio?.()
  if (!p) return
  form.value.reference_path = p
}

function clearReferencePath() {
  form.value.reference_path = ''
}

// ====== 音频编辑器相关 ======
const waveEditorKey = ref(null)

function handleWaveReady(ws) {
  console.log('WaveCellPro ready', ws)
}

// 处理音频编辑确认
async function handleWaveConfirm(payload) {
  if (!editingVoice.value?.reference_path) return
  
  try {
    const res = await processVoiceAudio(editingVoice.value.reference_path, {
      speed: payload.speed,
      volume: payload.volume,
      start_ms: payload.start_ms,
      end_ms: payload.end_ms,
      silence_sec: payload.silence_sec,
      current_ms: payload.current_ms
    })
    
    if (res.code === 200) {
      ElMessage.success('音频处理完成')
      // 刷新编辑器
      waveEditorKey.value = Date.now()
    } else {
      ElMessage.error(res.message || '音频处理失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('音频处理失败')
  }
}

function toFileUrl(p) {
  try { return native.pathToFileUrl(p) } catch { return '' }
}

function submitForm() {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const payload = {
        name: form.value.name,
        description: form.value.tags.length ? form.value.tags.join(',') : null,
        tts_provider_id: form.value.tts_provider_id,
        reference_path: form.value.reference_path || null
      }

      if (form.value.id) {
        // 添加id
        payload.id = form.value.id
        await updateVoice(form.value.id, payload)
        ElMessage.success('修改成功')
      } else {
        
        await createVoice(payload)
        ElMessage.success('创建成功')
      }

      dialogVisible.value = false
      await loadVoices()
    } catch (e) {
      console.error(e)
      ElMessage.error('操作失败')
    }
  })
}

async function handleDelete(id) {
  try {
    audioPlayer.pause()
    await deleteVoice(id)
    ElMessage.success('删除成功')
    await loadVoices()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function handleBatchDelete() {
  const ids = selectedIds.value
  if (!ids.length) {
    ElMessage.warning('请先选择要删除的音色')
    return
  }

  audioPlayer.pause()

  const results = await Promise.allSettled(
    ids.map(id =>
      deleteVoice(id).then(res => {
        if (res?.code !== 200) throw new Error(res?.message || '删除失败')
        return res
      })
    )
  )

  const failed = results.filter(r => r.status === 'rejected')
  const successCount = ids.length - failed.length

  if (failed.length === 0) {
    ElMessage.success(`删除成功：${successCount} 个`)
  } else {
    ElMessage.warning(`删除完成：成功 ${successCount} 个，失败 ${failed.length} 个`)
  }

  await loadVoices()
}

onMounted(async () => {
  await loadTTS()
})

const tagSelectRef = ref(null)

function handleTagChange() {
  // 等 DOM 更新完再收起下拉框
  setTimeout(() => {
    tagSelectRef.value?.blur()
  }, 0)
}

function handleFilterTagChange() {
  setTimeout(() => {
    filterSelectRef.value?.blur()
  }, 0)
}

function resetFilters() {
  searchName.value = ''
  filterTags.value = []
}

async function handleExportSelected() {
  if (!selectedTTS.value) {
    ElMessage.warning('请先选择 TTS 引擎')
    return
  }
  const ids = selectedIds.value
  if (ids.length === 0) {
    ElMessage.warning('请先选择要导出的音色')
    return
  }

  try {
    const savePath = await native?.saveFile?.({
      title: '导出选中音色',
      defaultPath: 'voices_selected_export.zip',
      filters: [{ name: 'ZIP 文件', extensions: ['zip'] }]
    })

    if (!savePath) return

    const res = await exportVoices(selectedTTS.value, savePath, ids)
    if (res.code === 200) {
      ElMessage.success('导出成功：' + savePath)
    } else {
      ElMessage.error(res.message || '导出失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  }
}

// ====== 导入音色库弹窗 ======
const importDialogVisible = ref(false)
const importForm = ref({
  zipPath: '',
  targetDir: ''
})

// 获取默认音色保存目录
// 注意:Tauri 的 getUserHome 是异步的,此函数需 await 调用
async function getDefaultVoiceDir() {
  // 默认为用户目录下的 SonicVale/voices
  const userHome = (await native?.getUserHome?.()) || ''
  return userHome ? `${userHome}/SonicVale/voices` : ''
}

// 选择导入的zip文件
async function pickImportZip() {
  const zipPath = await native?.pickFile?.({
    title: '选择音色库文件',
    filters: [{ name: 'ZIP 文件', extensions: ['zip'] }]
  })
  if (zipPath) {
    importForm.value.zipPath = zipPath
  }
}

// 选择导入目标目录
async function pickImportDir() {
  const dir = await native?.pickDirectory?.({
    title: '选择音色保存目录'
  })
  if (dir) {
    importForm.value.targetDir = dir
  }
}

// 打开导入弹窗
async function handleImport() {
  if (!selectedTTS.value) {
    ElMessage.warning('请先选择 TTS 引擎')
    return
  }
  
  // 设置默认值
  importForm.value = {
    zipPath: '',
    targetDir: await getDefaultVoiceDir()
  }
  importDialogVisible.value = true
}

// 确认导入
async function confirmImport() {
  if (!importForm.value.zipPath) {
    ElMessage.warning('请选择音色库文件')
    return
  }
  if (!importForm.value.targetDir) {
    ElMessage.warning('请设置音色保存目录')
    return
  }

  try {
    const res = await importVoices(
      selectedTTS.value, 
      importForm.value.zipPath, 
      importForm.value.targetDir
    )
    if (res.code === 200) {
      const data = res.data
      let msg = `导入完成：成功 ${data.success_count} 个`
      if (data.skipped_count > 0) {
        msg += `，跳过 ${data.skipped_count} 个（名称已存在）`
      }
      ElMessage.success(msg)
      importDialogVisible.value = false
      await loadVoices() // 刷新列表
    } else {
      ElMessage.error(res.message || '导入失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('导入失败')
  }
}

// ====== 复制音色弹窗 ======
const copyDialogVisible = ref(false)
const copyFormRef = ref(null)
const copyForm = ref({
  sourceId: null,
  sourceName: '',
  newName: '',
  targetDir: ''
})

const copyRules = {
  newName: [{ required: true, message: '请输入新音色名称', trigger: 'blur' }]
}

// 打开复制弹窗
function openCopyDialog(row) {
  copyForm.value = {
    sourceId: row.id,
    sourceName: row.name,
    newName: row.name + '_复制',
    targetDir: ''
  }
  copyDialogVisible.value = true
}

// 选择复制目标目录
async function pickCopyTargetDir() {
  const dir = await native?.pickDirectory?.({
    title: '选择新音色保存目录'
  })
  if (dir) {
    copyForm.value.targetDir = dir
  }
}

// 确认复制
async function confirmCopy() {
  if (!copyForm.value.newName) {
    ElMessage.warning('请输入新音色名称')
    return
  }

  try {
    const res = await copyVoice(
      copyForm.value.sourceId,
      copyForm.value.newName,
      copyForm.value.targetDir || null
    )
    if (res.code === 200) {
      ElMessage.success('复制成功')
      copyDialogVisible.value = false
      await loadVoices() // 刷新列表
    } else {
      ElMessage.error(res.message || '复制失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('复制失败')
  }
}

// ====== 火山引擎声音复刻 ======
const volcanoCloneDialogVisible = ref(false)
const volcanoCloneFormRef = ref(null)
const volcanoCloneForm = ref({
  name: '',
  speaker_id: '',
  model_type: 1,
  language: 0,
  description: ''
})

const volcanoCloneRules = {
  name: [{ required: true, message: '请输入音色名称', trigger: 'blur' }],
  speaker_id: [{ required: true, message: '请输入 Speaker ID', trigger: 'blur' }]
}

const volcanoUploadDialogVisible = ref(false)
const volcanoUploadClone = ref({ name: '' })
const volcanoUploadForm = ref({
  reference_path: '',
  text: '',
  enable_denoise: true
})

// 火山 clone 辅助函数
function cloneStatusName(status) {
  const map = { 0: '待上传', 1: '训练中', 2: '成功', 3: '失败', 4: '已激活' }
  return map[status] || '未知'
}

function cloneStatusTagType(status) {
  const map = { 0: 'info', 1: 'warning', 2: 'success', 3: 'danger', 4: 'success' }
  return map[status] || 'info'
}

function openVolcanoCloneDialog() {
  volcanoCloneForm.value = {
    name: '',
    speaker_id: '',
    model_type: 1,
    language: 0,
    description: ''
  }
  volcanoCloneDialogVisible.value = true
}

async function submitVolcanoClone() {
  volcanoCloneFormRef.value?.validate(async (valid) => {
    if (!valid) return
    try {
      const res = await createVoiceClone({
        ...volcanoCloneForm.value,
        tts_provider_id: selectedTTS.value
      })
      if (res.code === 200) {
        ElMessage.success('复刻记录创建成功')
        volcanoCloneDialogVisible.value = false
        await loadVoices()
      } else {
        ElMessage.error(res.message || '创建失败')
      }
    } catch (e) {
      console.error(e)
      ElMessage.error('创建失败')
    }
  })
}

async function pickVolcanoAudioFile() {
  const p = await native?.pickAudio?.()
  if (p) {
    volcanoUploadForm.value.reference_path = p
  }
}

function openVolcanoUploadDialog(clone) {
  volcanoUploadClone.value = clone
  volcanoUploadForm.value = {
    reference_path: clone.reference_path || '',
    text: '',
    enable_denoise: true
  }
  volcanoUploadDialogVisible.value = true
}

async function submitVolcanoUpload() {
  if (!volcanoUploadForm.value.reference_path) {
    ElMessage.warning('请选择音频文件')
    return
  }
  try {
    const res = await uploadAudio({
      clone_id: volcanoUploadClone.value.id,
      reference_path: volcanoUploadForm.value.reference_path,
      text: volcanoUploadForm.value.text || undefined,
      enable_denoise: volcanoUploadForm.value.enable_denoise
    })
    if (res.code === 200) {
      ElMessage.success('音频上传成功，训练中')
      volcanoUploadDialogVisible.value = false
      await loadVoices()
    } else {
      ElMessage.error(res.message || '上传失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('上传失败: ' + (e.response?.data?.message || e.message))
  }
}

async function handleRefreshCloneStatus(clone) {
  try {
    await queryStatus(clone.id)
    ElMessage.success('状态已更新')
    await loadVoices()
  } catch (e) {
    console.error(e)
    ElMessage.error('查询状态失败')
  }
}

async function handleDeleteClone(clone) {
  try {
    const res = await deleteVoiceClone(clone.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      await loadVoices()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

</script>

<style scoped>
.tag-hint {
  font-size: 12px;
  color: #409EFF; /* Element Plus 主色蓝 */
  margin-bottom: 6px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.page-header h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.filter-tags {
  width: 260px;
}
.filter-search {
  width: 220px;
}
.filter-result {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.tts-select {
  width: 240px;
}
.voice-table {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}
.tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.path-ellipsis {
  display: inline-block;
  max-width: 380px;
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-regular);
}
.pick-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.path-text {
  font-size: 12px;
  color: var(--el-text-color-regular);
  word-break: break-all;
}
.mb8 {
  margin-bottom: 8px;
}
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.wave-editor-wrap {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  border: 1px solid var(--el-border-color);
}
.audio-editor-info {
  margin-bottom: 16px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
.audio-editor-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.audio-editor-value {
  color: var(--el-text-color-primary);
  font-weight: 600;
  font-size: 14px;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 8px 0;
}
.no-audio-tip {
  color: var(--el-text-color-placeholder);
  font-size: 14px;
}
</style>
