<template>
  <div class="gop">
    <div class="gop-row">
      <el-select v-model="layer" size="small" class="gop-lt" @change="onLayer">
        <el-option v-for="l in layers" :key="l" :label="l" :value="l" />
      </el-select>
      <el-select v-model="type" size="small" class="gop-lt" @change="onType">
        <el-option v-for="t in types" :key="t" :label="t" :value="t" />
      </el-select>
    </div>
    <el-select
      v-model="selected"
      multiple
      filterable
      remote
      :remote-method="onSearch"
      :loading="loading"
      collapse-tags
      collapse-tags-tooltip
      size="small"
      class="gop-pick"
      :placeholder="`选/搜 ${type}（中英文均可，可多选）`"
      no-data-text="输入关键词搜索"
    >
      <el-option v-for="o in options" :key="o.id" :label="o.name + '（' + o.id + '）'" :value="o.id" />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElSelect, ElOption } from 'element-plus'
import { LAYER_TYPES, fetchGraphObjects, getNameMap } from '../api'

const props = defineProps<{ modelValue: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()

const layers = Object.keys(LAYER_TYPES)
const layer = ref(layers[0])
const type = ref(LAYER_TYPES[layers[0]][0])
const types = computed(() => LAYER_TYPES[layer.value] || [])

const loading = ref(false)
const options = ref<{ id: string; name: string }[]>([])
const nameMap = ref<Record<string, string>>({})

const selected = computed<string[]>({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

async function load(q = ''): Promise<void> {
  loading.value = true
  try {
    const res = await fetchGraphObjects(type.value, q)
    res.forEach((r) => {
      nameMap.value[r.id] = r.name
    })
    // 已选项始终保留在 options 里（保证跨类型切换时 tag 显可读名）
    const selObjs = props.modelValue
      .filter((id) => !res.find((r) => r.id === id))
      .map((id) => ({ id, name: nameMap.value[id] || id }))
    options.value = [...res, ...selObjs]
  } finally {
    loading.value = false
  }
}

function onLayer(): void {
  type.value = types.value[0] || ''
  load()
}
function onType(): void {
  load()
}
function onSearch(q: string): void {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => load(q || ''), 250)
}
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 编辑模式预填：给已选 id 补可读名 + 初始下拉项
onMounted(async () => {
  try {
    const m = await getNameMap()
    props.modelValue.forEach((id) => {
      const n = m.get(id)
      if (n) nameMap.value[id] = n
    })
  } catch {
    /* 容错 */
  }
  load()
})
</script>

<style scoped>
.gop {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.gop-row {
  display: flex;
  gap: 6px;
}
.gop-lt {
  width: 50%;
}
.gop-pick {
  width: 100%;
}
</style>
