<template>
  <div class="login-screen">
    <!-- 左：品牌氛围（深 indigo + 图谱节点网络） -->
    <aside class="login-aside">
      <svg class="graph-net" viewBox="0 0 480 480" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <g class="net-lines" stroke="currentColor" stroke-width="1" opacity="0.35">
          <line x1="80" y1="90" x2="220" y2="70" />
          <line x1="220" y1="70" x2="380" y2="140" />
          <line x1="80" y1="90" x2="140" y2="240" />
          <line x1="140" y1="240" x2="300" y2="300" />
          <line x1="380" y1="140" x2="300" y2="300" />
          <line x1="300" y1="300" x2="180" y2="400" />
          <line x1="140" y1="240" x2="60" y2="360" />
          <line x1="220" y1="70" x2="140" y2="240" />
          <line x1="380" y1="140" x2="420" y2="320" />
          <line x1="300" y1="300" x2="420" y2="320" />
        </g>
        <g class="net-dots" fill="currentColor">
          <circle class="d d1" cx="80" cy="90" r="4" />
          <circle class="d d2" cx="220" cy="70" r="6" opacity="0.9" />
          <circle class="d d3" cx="380" cy="140" r="4" />
          <circle class="d d4" cx="140" cy="240" r="5" opacity="0.85" />
          <circle class="d d5" cx="300" cy="300" r="7" />
          <circle class="d d6" cx="180" cy="400" r="4" opacity="0.8" />
          <circle class="d d7" cx="60" cy="360" r="3" />
          <circle class="d d8" cx="420" cy="320" r="4" opacity="0.85" />
        </g>
      </svg>

      <div class="aside-glow" aria-hidden="true" />

      <div class="aside-content">
        <div class="aside-brand">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" class="aside-mark">
            <circle cx="6" cy="6" r="2.4" fill="currentColor" />
            <circle cx="18" cy="6" r="2.4" fill="currentColor" opacity="0.6" />
            <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.8" />
            <path d="M6 6 L18 6 M6 6 L12 18 M18 6 L12 18" stroke="currentColor" stroke-width="1.2" opacity="0.45" />
          </svg>
        </div>

        <div class="aside-tagline">
          <h1 class="aside-title">图谱资产平台</h1>
          <p class="aside-sub">三层图谱 · 配置生成 · 数据飞轮</p>
        </div>

        <div class="aside-foot">
          <span class="foot-dot" /> 受控访问 · 全量审计
        </div>
      </div>
    </aside>

    <!-- 右：登录表单 -->
    <main class="login-main">
      <form class="login-card" @submit.prevent="onSubmit">
        <header class="card-head">
          <div class="card-mark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle cx="6" cy="7" r="2.2" stroke="currentColor" stroke-width="1.7" />
              <circle cx="18" cy="7" r="2.2" stroke="currentColor" stroke-width="1.7" />
              <circle cx="12" cy="17" r="2.2" stroke="currentColor" stroke-width="1.7" />
              <path d="M7.8 8.3 16.2 8.3 M7 8.7 10.8 15 M17 8.7 13.2 15" stroke="currentColor" stroke-width="1.5" opacity="0.7" />
            </svg>
          </div>
          <h2 class="card-title">登录</h2>
          <p class="card-sub">输入用户名与访问 KEY</p>
        </header>

        <label class="field">
          <span class="field-label">用户名</span>
          <input
            v-model="username"
            class="field-input"
            type="text"
            placeholder="用户名"
            autofocus
            autocomplete="username"
          />
        </label>

        <label class="field">
          <span class="field-label">API Key</span>
          <input
            v-model="key"
            class="field-input"
            type="password"
            placeholder="访问密钥"
            autocomplete="current-password"
          />
        </label>

        <transition name="err-pop">
          <p v-if="err" class="field-err">{{ err }}</p>
        </transition>

        <button
          type="submit"
          class="submit-btn"
          :disabled="loading || !username.trim() || !key.trim()"
        >
          <span v-if="!loading">进入平台</span>
          <span v-else class="spinner" aria-label="验证中" />
        </button>

        <p class="card-hint">仅授权用户可访问 · SKILL 调用见接口文档</p>
      </form>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { setSession } from '../auth'
import { login } from '../api'

const username = ref('')
const key = ref('')
const err = ref('')
const loading = ref(false)

async function onSubmit(): Promise<void> {
  loading.value = true
  err.value = ''
  try {
    const u = await login(username.value.trim(), key.value.trim())
    setSession({
      username: u.username,
      key: key.value.trim(),
      can_frontend: u.can_frontend,
      can_assets: u.can_assets,
      can_upload: u.can_upload,
      can_test: u.can_test,
      can_skill: u.can_skill,
      is_admin: u.is_admin,
    })
    window.location.assign('/')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '登录失败'
    err.value = /401|未授权|用户名|KEY/i.test(msg) ? '用户名或 KEY 错误' : msg
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-screen {
  height: 100%;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: var(--bg);
}

/* ---------- 左：品牌氛围 ---------- */
.login-aside {
  position: relative;
  overflow: hidden;
  color: #e0e7ff;
  background:
    radial-gradient(900px 500px at 20% 110%, rgba(99, 102, 241, 0.55) 0%, transparent 60%),
    radial-gradient(700px 400px at 90% 0%, rgba(167, 139, 250, 0.4) 0%, transparent 55%),
    linear-gradient(160deg, #312e81 0%, #3730a3 45%, #4338ca 100%);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-8);
}

.graph-net {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: #c7d2fe;
  opacity: 0.85;
}
.net-lines {
  animation: net-pulse 6s var(--ease) infinite;
}
.net-dots .d {
  transform-box: fill-box;
  transform-origin: center;
  filter: drop-shadow(0 0 6px rgba(199, 210, 254, 0.6));
}
.d1 { animation: float-a 7s var(--ease) infinite; }
.d2 { animation: float-b 9s var(--ease) infinite; }
.d3 { animation: float-a 8s var(--ease) infinite reverse; }
.d4 { animation: float-b 6s var(--ease) infinite; }
.d5 { animation: float-a 10s var(--ease) infinite; }
.d6 { animation: float-b 7.5s var(--ease) infinite reverse; }
.d7 { animation: float-a 6.5s var(--ease) infinite; }
.d8 { animation: float-b 8.5s var(--ease) infinite; }

@keyframes float-a {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(6px, -8px); }
}
@keyframes float-b {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-7px, 6px); }
}
@keyframes net-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.5; }
}

.aside-glow {
  position: absolute;
  width: 60%;
  height: 60%;
  right: -10%;
  top: -10%;
  background: radial-gradient(circle, rgba(196, 181, 253, 0.35) 0%, transparent 70%);
  filter: blur(40px);
  pointer-events: none;
}

.aside-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
}
.aside-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.aside-mark {
  opacity: 0.95;
}
.aside-name {
  font-family: var(--display);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.aside-tagline {
  margin-top: auto;
  margin-bottom: auto;
}
.aside-title {
  font-family: var(--display);
  font-size: clamp(40px, 5vw, 64px);
  font-weight: 700;
  line-height: 1.02;
  letter-spacing: -0.03em;
  margin: 0;
  color: #fff;
}
.aside-sub {
  margin: var(--space-5) 0 0;
  font-size: 14px;
  color: #c7d2fe;
  letter-spacing: 0.02em;
}
.aside-foot {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: #a5b4fc;
  letter-spacing: 0.04em;
}
.foot-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #a5b4fc;
  box-shadow: 0 0 0 4px rgba(165, 180, 252, 0.18);
  animation: dot-pulse 2.4s var(--ease) infinite;
}
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(165, 180, 252, 0.18); }
  50% { box-shadow: 0 0 0 8px rgba(165, 180, 252, 0.05); }
}

/* ---------- 右：登录表单 ---------- */
.login-main {
  display: grid;
  place-items: center;
  padding: var(--space-8);
}
.login-card {
  width: 100%;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: card-rise 0.6s var(--ease) both;
}
@keyframes card-rise {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.card-head {
  margin-bottom: var(--space-2);
  animation: rise 0.5s var(--ease) both;
}
.card-mark {
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
  display: grid;
  place-items: center;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid var(--border);
  margin-bottom: var(--space-4);
}
.card-title {
  font-family: var(--display);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--text);
}
.card-sub {
  margin: var(--space-1) 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  animation: rise 0.5s var(--ease) both;
}
.field:nth-of-type(1) { animation-delay: 60ms; }
.field:nth-of-type(2) { animation-delay: 120ms; }
@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}
.field-input {
  width: 100%;
  padding: 11px 13px;
  font-size: 14px;
  font-family: var(--sans);
  color: var(--text);
  background: var(--bg-elev);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}
.field-input::placeholder {
  color: var(--text-faint);
}
.field-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.field-err {
  margin: -4px 0 0;
  padding: 8px 12px;
  font-size: 12.5px;
  color: var(--danger);
  background: rgba(239, 68, 68, 0.07);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-sm);
  animation: shake 0.4s var(--ease);
}
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-5px); }
  40%, 80% { transform: translateX(5px); }
}
.err-pop-enter-active,
.err-pop-leave-active {
  transition: opacity var(--dur-fast) var(--ease);
}
.err-pop-enter-from,
.err-pop-leave-to {
  opacity: 0;
}

.submit-btn {
  margin-top: var(--space-2);
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--sans);
  color: #fff;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.2);
  animation: rise 0.5s var(--ease) both;
  animation-delay: 180ms;
}
.submit-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(79, 70, 229, 0.3);
}
.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}
.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.card-hint {
  margin: var(--space-3) 0 0;
  font-size: 11.5px;
  color: var(--text-faint);
  text-align: center;
  letter-spacing: 0.02em;
}

/* ---------- 响应式：窄屏只显示表单 ---------- */
@media (max-width: 860px) {
  .login-screen {
    grid-template-columns: 1fr;
  }
  .login-aside {
    display: none;
  }
}
</style>
