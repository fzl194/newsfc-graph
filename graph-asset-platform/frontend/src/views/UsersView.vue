<template>
  <div class="users-page">
    <header class="page-head stagger-in">
      <div>
        <h1 class="page-title">用户管理</h1>
        <p class="page-sub">维护账号、权限与访问密钥</p>
      </div>
      <el-button type="primary" @click="openCreate">+ 新建用户</el-button>
    </header>

    <div class="table-card stagger-in">
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column label="API Key" min-width="300">
          <template #default="{ row }">
            <div class="key-cell">
              <code class="key">{{ row.key }}</code>
              <button class="copy-btn" title="复制 KEY" @click="copy(row.key)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                  <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.7" />
                  <path d="M5 15V5a2 2 0 0 1 2-2h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
                </svg>
              </button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="权限" width="240">
          <template #default="{ row }">
            <div class="perm-tags">
              <span v-if="row.is_admin" class="perm-tag perm-admin">admin</span>
              <span v-if="row.can_frontend" class="perm-tag perm-frontend">前端</span>
              <span v-if="row.can_assets" class="perm-tag perm-assets">资产</span>
              <span v-if="row.can_upload" class="perm-tag perm-upload">上传</span>
              <span v-if="row.can_test" class="perm-tag perm-test">测试</span>
              <span v-if="row.can_skill" class="perm-tag perm-skill">SKILL</span>
              <span
                v-if="!row.is_admin && !row.can_frontend && !row.can_assets && !row.can_upload && !row.can_test && !row.can_skill"
                class="perm-none"
              >无</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link size="small" @click="openActivity(row as UserRow)">轨迹</el-button>
              <el-button link size="small" @click="openEdit(row as UserRow)">改权限</el-button>
              <el-button link size="small" type="danger" :disabled="row.username === 'admin'" @click="del(row as UserRow)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新建用户 -->
    <el-dialog v-model="createVisible" title="新建用户" width="440px">
      <el-form label-width="92px" class="user-form">
        <el-form-item label="用户名"><el-input v-model="form.username" placeholder="登录用用户名" /></el-form-item>
        <el-form-item label="前端权限"><el-checkbox v-model="form.can_frontend" /></el-form-item>
        <el-form-item label="资产权限"><el-checkbox v-model="form.can_assets" /></el-form-item>
        <el-form-item label="上传权限"><el-checkbox v-model="form.can_upload" /></el-form-item>
        <el-form-item label="测试权限"><el-checkbox v-model="form.can_test" /></el-form-item>
        <el-form-item label="SKILL权限"><el-checkbox v-model="form.can_skill" /></el-form-item>
        <el-form-item label="管理员"><el-checkbox v-model="form.is_admin" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doCreate">创建（自动生成 KEY）</el-button>
      </template>
    </el-dialog>

    <!-- 改权限 / 重置 KEY -->
    <el-dialog v-model="editVisible" title="修改权限 / 重置 KEY" width="440px">
      <el-form label-width="92px" class="user-form">
        <el-form-item label="用户名"><span class="form-username">{{ editTarget?.username }}</span></el-form-item>
        <el-form-item label="前端权限"><el-checkbox v-model="editForm.can_frontend" /></el-form-item>
        <el-form-item label="资产权限"><el-checkbox v-model="editForm.can_assets" /></el-form-item>
        <el-form-item label="上传权限"><el-checkbox v-model="editForm.can_upload" /></el-form-item>
        <el-form-item label="测试权限"><el-checkbox v-model="editForm.can_test" /></el-form-item>
        <el-form-item label="SKILL权限"><el-checkbox v-model="editForm.can_skill" /></el-form-item>
        <el-form-item label="管理员"><el-checkbox v-model="editForm.is_admin" /></el-form-item>
        <el-form-item label="API KEY">
          <el-radio-group v-model="editForm.keyMode">
            <el-radio value="keep">保持不变</el-radio>
            <el-radio value="random">随机重置</el-radio>
            <el-radio value="custom">自定义</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="editForm.keyMode === 'custom'" label="新 KEY">
          <el-input v-model="editForm.setKey" placeholder="≥8 位且不含空格（如 udg-team-2026）" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 行为轨迹 -->
    <el-drawer v-model="activityVisible" :title="`行为轨迹 - ${activityTarget?.username}`" size="50%">
      <div v-if="!activityLoading && !activity.length" class="drawer-empty">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" opacity="0.4" />
          <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        <div class="drawer-empty-title">近 30 天无行为记录</div>
      </div>
      <el-table v-else :data="activity" v-loading="activityLoading" size="small">
        <el-table-column prop="ts" label="时间" width="180" />
        <el-table-column prop="endpoint" label="接口" min-width="200" />
        <el-table-column prop="caller" label="来源" width="80" />
        <el-table-column prop="operator" label="工号" width="100" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  ElButton, ElTable, ElTableColumn, ElDialog, ElForm, ElFormItem, ElInput,
  ElCheckbox, ElDrawer, ElMessage, ElMessageBox, ElRadio, ElRadioGroup,
} from 'element-plus'
import {
  listUsers, createUser, updateUser, deleteUser, userActivity, type UserRow,
} from '../api'
import { getSession, setSession } from '../auth'

const users = ref<UserRow[]>([])
const loading = ref(false)
const saving = ref(false)

const createVisible = ref(false)
const form = reactive({
  username: '',
  can_frontend: false,
  can_assets: false,
  can_upload: false,
  can_test: false,
  can_skill: false,
  is_admin: false,
})

const editVisible = ref(false)
const editTarget = ref<UserRow | null>(null)
const editForm = reactive({
  can_frontend: false,
  can_assets: false,
  can_upload: false,
  can_test: false,
  can_skill: false,
  is_admin: false,
  keyMode: 'keep' as 'keep' | 'random' | 'custom',
  setKey: '',
})

const activityVisible = ref(false)
const activityTarget = ref<UserRow | null>(null)
const activity = ref<{ ts: string; endpoint: string; caller: string; operator: string }[]>([])
const activityLoading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  Object.assign(form, {
    username: '',
    can_frontend: false,
    can_assets: false,
    can_upload: false,
    can_test: false,
    can_skill: false,
    is_admin: false,
  })
  createVisible.value = true
}

async function doCreate(): Promise<void> {
  if (!form.username.trim()) return
  saving.value = true
  try {
    const u = await createUser({
      username: form.username.trim(),
      can_frontend: form.can_frontend,
      can_assets: form.can_assets,
      can_upload: form.can_upload,
      can_test: form.can_test,
      can_skill: form.can_skill,
      is_admin: form.is_admin,
    })
    ElMessage.success(`已创建，KEY：${u.key}`)
    createVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}

function openEdit(row: UserRow): void {
  editTarget.value = row
  Object.assign(editForm, {
    can_frontend: row.can_frontend,
    can_assets: row.can_assets,
    can_upload: row.can_upload,
    can_test: row.can_test,
    can_skill: row.can_skill,
    is_admin: row.is_admin,
    keyMode: 'keep',
    setKey: '',
  })
  editVisible.value = true
}

async function doEdit(): Promise<void> {
  if (!editTarget.value) return
  const customKey = editForm.setKey.trim()
  if (editForm.keyMode === 'custom' && (customKey.length < 8 || /\s/.test(customKey))) {
    ElMessage.error('自定义 KEY 需 ≥8 位且不含空格')
    return
  }
  saving.value = true
  try {
    const patch: Record<string, unknown> = {
      can_frontend: editForm.can_frontend,
      can_assets: editForm.can_assets,
      can_upload: editForm.can_upload,
      can_test: editForm.can_test,
      can_skill: editForm.can_skill,
      is_admin: editForm.is_admin,
    }
    if (editForm.keyMode === 'random') patch.reset_key = true
    else if (editForm.keyMode === 'custom') patch.set_key = customKey
    const u = await updateUser(editTarget.value.username, patch)
    // 改的是当前登录账号自己的 KEY → 同步 sessionStorage，否则下一请求即 401
    const s = getSession()
    if (s && s.username === editTarget.value.username && u.key !== s.key) {
      setSession({ ...s, key: u.key })
      ElMessage.warning('已修改当前登录账号的 KEY，会话凭证已同步')
    } else {
      ElMessage.success('已保存')
    }
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function del(row: UserRow): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteUser(row.username)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

async function openActivity(row: UserRow): Promise<void> {
  activityTarget.value = row
  activityVisible.value = true
  activityLoading.value = true
  try {
    activity.value = await userActivity(row.username, 30)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    activityLoading.value = false
  }
}

function copy(k: string): void {
  navigator.clipboard?.writeText(k).then(() => ElMessage.success('已复制 KEY'))
}

onMounted(load)
</script>

<style scoped>
.users-page {
  height: 100%;
  overflow: auto;
  padding: var(--space-8) var(--space-6);
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* 统一页头（与其他视图 page-head 数值对齐） */
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.page-title {
  font-family: var(--display);
  font-size: 26px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
  letter-spacing: -0.02em;
}
.page-sub {
  margin: var(--space-2) 0 0;
  color: var(--text-muted);
  font-size: 13px;
}

/* 表格卡片化 */
.table-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* KEY 单元格：mono + 可复制感 */
.key-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.key {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text);
  background: var(--bg-sunken);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  letter-spacing: 0.02em;
}
.copy-btn {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elev);
  color: var(--text-faint);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease);
}
.copy-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

/* 权限标签：token 化、层次分明 */
.perm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.perm-tag {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  line-height: 1.5;
  border: 1px solid transparent;
  white-space: nowrap;
}
.perm-admin {
  color: var(--danger);
  background: rgba(220, 38, 38, 0.08);
  border-color: rgba(220, 38, 38, 0.2);
}
.perm-frontend {
  color: var(--success);
  background: rgba(5, 150, 105, 0.1);
  border-color: rgba(5, 150, 105, 0.22);
}
.perm-assets {
  color: #0e7490;
  background: rgba(14, 116, 144, 0.1);
  border-color: rgba(14, 116, 144, 0.24);
}
.perm-upload {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: rgba(79, 70, 229, 0.22);
}
.perm-test {
  color: var(--text-muted);
  background: var(--bg-sunken);
  border-color: var(--border);
}
.perm-skill {
  color: var(--warn);
  background: rgba(217, 119, 6, 0.1);
  border-color: rgba(217, 119, 6, 0.24);
}
.perm-none {
  font-size: 11.5px;
  color: var(--text-faint);
}

.row-actions {
  display: inline-flex;
  gap: 2px;
}

/* 对话框表单：label 对齐、checkbox 视觉居中 */
.user-form :deep(.el-form-item) {
  margin-bottom: var(--space-3);
}
.user-form :deep(.el-checkbox) {
  height: 32px;
}
.form-username {
  font-weight: 600;
  color: var(--text);
}

/* 抽屉空态 */
.drawer-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-10) var(--space-4);
  text-align: center;
  color: var(--text-faint);
}
.drawer-empty-title {
  font-size: 13px;
  color: var(--text-muted);
}
</style>
