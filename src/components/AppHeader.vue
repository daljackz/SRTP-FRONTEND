<script setup>
</script>

<template>
  <el-menu 
    mode="horizontal" 
    background-color="#304156" 
    text-color="#bfcbd9" 
    active-text-color="#409eff"
    router
    default-active="/"
    style="border-bottom: none;"
  >
    <div style="width: 200px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 18px;">
      高铁接驳调度 SRTP
    </div>

    <el-menu-item index="/">实时大屏</el-menu-item>
    <el-menu-item index="/info">调度信息</el-menu-item>
    <el-menu-item index="/logs">调度日志</el-menu-item>
    <el-menu-item index="/profile">个人信息</el-menu-item>
    <el-menu-item index="/about">关于我们</el-menu-item>
  </el-menu>
</template>