<template>
  <div class="ops-view">
    <div class="ops-container">
      <header class="page-head stagger-in">
        <div>
          <h1 class="page-title">运维</h1>
          <p class="page-sub">平台运行统计：知识取用频次（SKILL / MCP 打点聚合）</p>
        </div>
      </header>

      <TelemetrySection />
    </div>
  </div>
</template>

<script setup lang="ts">
import TelemetrySection from '../components/TelemetrySection.vue'
</script>

<style scoped>
.ops-view {
  height: 100%;
  overflow: auto;
  padding: var(--space-8) var(--space-6);
}

.ops-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

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
</style>
