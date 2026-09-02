<template>
  <AppHeader v-if="!isLogin" />
  <main class="app-main" :class="{ 'app-main--login': isLogin }">
    <router-view v-slot="{ Component }">
      <transition name="view-fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
const isLogin = computed(() => route.name === 'login')

// 右上角对象/边计数 chips 已按用户要求移除（2026-09-02）——全站 stats 拉取
// 随之取消；window.__refreshStats 现由 StatsView 链式注册（上传后刷新统计页）。
</script>

<style scoped>
.app-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.view-fade-enter-active,
.view-fade-leave-active {
  transition: opacity var(--dur) var(--ease), transform var(--dur) var(--ease);
}

.view-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.view-fade-leave-to {
  opacity: 0;
}
</style>
