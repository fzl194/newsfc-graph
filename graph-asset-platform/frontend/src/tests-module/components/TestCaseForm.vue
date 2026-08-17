<template>
  <div class="case-form">
    <h3 class="form-title">{{ isEdit ? '编辑测试用例' : '新建测试用例' }}</h3>

    <div class="row">
      <div class="field flex2">
        <label>用例名称 <span class="req">*</span></label>
        <el-input v-model="name" placeholder="如：离线计费-基础开通" />
      </div>
      <div class="field">
        <label>slug（用例 ID 后缀）</label>
        <el-input v-model="slug" :disabled="isEdit" placeholder="英文，如 charging-offline-basic" />
      </div>
    </div>

    <div class="row">
      <div class="field">
        <label>业务域 <span class="hint">关联图谱 BusinessDomain</span></label>
        <el-select v-model="domain" filterable allow-create default-first-option clearable placeholder="选或输入域" class="sel">
          <el-option v-for="d in domainOptions" :key="d.slug" :label="d.name + '（' + d.slug + '）'" :value="d.slug" />
        </el-select>
      </div>
      <div class="field">
        <label>场景 <span class="hint">关联图谱 NetworkScenario</span></label>
        <el-select v-model="scenario" filterable allow-create default-first-option clearable
          :disabled="!domain" :placeholder="domain ? '选或输入场景' : '先选业务域'" class="sel">
          <el-option v-for="s in scenarioOptions" :key="s.slug" :label="s.name + '（' + s.slug + '）'" :value="s.slug" />
        </el-select>
      </div>
      <div class="field">
        <label>编写人</label>
        <el-input v-model="author" placeholder="如 SA-zhang" />
      </div>
    </div>

    <div class="row">
      <div class="field flex2">
        <label>方案 <span class="hint">关联图谱 ConfigurationSolution（可选）</span></label>
        <el-select v-model="solution" filterable allow-create default-first-option clearable
          :disabled="!domain || !scenario" :placeholder="(!domain || !scenario) ? '先选业务域和场景' : '选或输入方案'" class="sel">
          <el-option v-for="s in solutionOptions" :key="s.id" :label="s.name + '（' + s.id + '）'" :value="s.id" />
        </el-select>
      </div>
    </div>

    <div class="field">
      <label>意图描述（业务诉求）<span class="req">*</span></label>
      <el-input v-model="intent" type="textarea" :rows="5" placeholder="这个用例测什么：业务诉求、网元/版本、关注点……" />
    </div>

    <div v-if="isEdit && existingFiles.length" class="field">
      <label>现有附件（勾选则删除）</label>
      <div class="exist-files">
        <label v-for="f in existingFiles" :key="f" class="exist-file">
          <input type="checkbox" :value="f" v-model="removeFiles" />
          <span class="ef-name">{{ f }}</span>
        </label>
      </div>
    </div>

    <div class="row">
      <div class="field flex2">
        <label>{{ isEdit ? '新增输入配置 txt（可选）' : '输入配置 txt（任意数量，可选）' }}</label>
        <input ref="inputFileEl" type="file" multiple class="file-input" @change="onInputFiles" />
        <div v-if="inputFiles.length" class="file-list">
          <span v-for="f in inputFiles" :key="f.name" class="file-chip">{{ f.name }}</span>
        </div>
      </div>
      <div class="field flex2">
        <label>{{ isEdit ? '新增参考输出配置 txt（可选）' : '参考输出配置 txt（任意数量，可选）' }}</label>
        <input ref="refFileEl" type="file" multiple class="file-input" @change="onRefFiles" />
        <div v-if="referenceFiles.length" class="file-list">
          <span v-for="f in referenceFiles" :key="f.name" class="file-chip">{{ f.name }}</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="err">{{ error }}</div>
    <div class="form-actions">
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!name.trim() || !intent.trim()" @click="submit">
        {{ isEdit ? '保存修改' : '建用例' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElInput, ElSelect, ElOption, ElButton } from 'element-plus'
import {
  createCase, updateCase, fetchBusinessDomains, fetchScenarios, fetchSolutions,
  type CaseDetail,
} from '../api'

const props = defineProps<{ case?: CaseDetail | null }>()
const emit = defineEmits<{ saved: [c: CaseDetail]; cancel: [] }>()

const isEdit = computed(() => !!props.case)
const name = ref(props.case?.name || '')
const slug = ref(props.case ? props.case.id.split('@')[1] || '' : '')
const domain = ref(props.case?.domain || '')
const scenario = ref(props.case?.scenario || '')
const solution = ref(props.case?.solution || '')
const author = ref((props.case?.author as string) || '')
const intent = ref(props.case?.body_md || '')
const inputFiles = ref<File[]>([])
const referenceFiles = ref<File[]>([])
const removeFiles = ref<string[]>([])
const inputFileEl = ref<HTMLInputElement | null>(null)
const refFileEl = ref<HTMLInputElement | null>(null)
const submitting = ref(false)
const error = ref('')

const existingFiles = computed(() => props.case?.files || [])
const domainOptions = ref<{ slug: string; name: string }[]>([])
const scenarioOptions = ref<{ slug: string; name: string }[]>([])
const solutionOptions = ref<{ id: string; name: string }[]>([])

async function loadDomains(): Promise<void> {
  try {
    domainOptions.value = await fetchBusinessDomains()
  } catch {
    /* 容错 */
  }
}
async function loadScenarios(): Promise<void> {
  if (!domain.value) {
    scenarioOptions.value = []
    return
  }
  try {
    scenarioOptions.value = await fetchScenarios(domain.value)
  } catch {
    scenarioOptions.value = []
  }
}
async function loadSolutions(): Promise<void> {
  if (!domain.value || !scenario.value) {
    solutionOptions.value = []
    return
  }
  try {
    solutionOptions.value = await fetchSolutions(domain.value, scenario.value)
  } catch {
    solutionOptions.value = []
  }
}

watch(domain, () => {
  scenario.value = ''
  solution.value = ''
  loadScenarios()
})
watch(scenario, () => {
  solution.value = ''
  loadSolutions()
})

onMounted(() => {
  loadDomains()
  loadScenarios()
  loadSolutions()
})

function onInputFiles(e: Event): void {
  inputFiles.value = Array.from((e.target as HTMLInputElement).files || [])
}
function onRefFiles(e: Event): void {
  referenceFiles.value = Array.from((e.target as HTMLInputElement).files || [])
}

async function submit(): Promise<void> {
  submitting.value = true
  error.value = ''
  try {
    let c: CaseDetail
    if (isEdit.value && props.case) {
      c = await updateCase(props.case.id, {
        name: name.value.trim(),
        intent: intent.value,
        domain: domain.value.trim(),
        scenario: scenario.value.trim(),
        solution: solution.value.trim(),
        inputFiles: inputFiles.value,
        referenceFiles: referenceFiles.value,
        removeFiles: removeFiles.value,
      })
    } else {
      c = await createCase({
        name: name.value.trim(),
        intent: intent.value,
        domain: domain.value.trim() || undefined,
        scenario: scenario.value.trim() || undefined,
        solution: solution.value.trim() || undefined,
        slug: slug.value.trim() || undefined,
        author: author.value.trim() || undefined,
        inputFiles: inputFiles.value,
        referenceFiles: referenceFiles.value,
      })
    }
    emit('saved', c)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.case-form {
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-5);
  margin-bottom: var(--space-5);
}
.form-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 var(--space-4);
}
.row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.field {
  flex: 1;
}
.flex2 {
  flex: 2;
}
.field label {
  display: block;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.hint {
  font-weight: 400;
  color: var(--text-faint);
  margin-left: 4px;
}
.sel {
  width: 100%;
}
.req {
  color: #dc2626;
}
.exist-files {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
}
.exist-file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text);
}
.ef-name {
  font-family: var(--mono);
  font-size: 11.5px;
}
.file-input {
  font-size: 12.5px;
  width: 100%;
}
.file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.file-chip {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11.5px;
  color: var(--text-muted);
  font-family: var(--mono);
}
.err {
  color: #dc2626;
  font-size: 12.5px;
  margin: var(--space-2) 0;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
