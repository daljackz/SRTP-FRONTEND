<script setup>
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
</script>

<template>
  <div class="common-layout">
    <el-container style="height: 100vh;">
      
      <el-header style="padding: 0;">
        <AppHeader />
      </el-header>

      <el-main style="background-color: #f0f2f5;">
        <router-view />
      </el-main>

      <el-footer style="background-color: #ffffff; text-align: center; line-height: 60px; border-top: 1px solid #dcdfe6;">
        <AppFooter />
      </el-footer>
      
    </el-container>
  </div>
</template>

<style>
/* 终极清空：干掉浏览器默认的页面白边 */
html, body {
  margin: 0;
  padding: 0;
}
</style>