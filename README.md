# 高铁枢纽接驳公交调度决策支持系统

本文说明小组成员如何在自己的 Windows 电脑上运行项目。下面所有命令都在 PowerShell 中执行，并且使用相对路径，项目文件夹可以放在任意盘符或目录，不需要修改命令中的路径。

## 一、打开项目文件夹中的 PowerShell

1. 解压收到的项目文件夹。
2. 在资源管理器中打开项目根目录，应当能看到 `package.json` 和 `backend_keep_internal` 文件夹。
3. 在文件夹空白处按住 `Shift` 并点击鼠标右键，选择“在此处打开 PowerShell 窗口”。
4. 也可以点击资源管理器地址栏，输入 `powershell` 后按 Enter。

先检查当前目录是否正确：

```powershell
Test-Path .\package.json
Test-Path .\backend_keep_internal\main.py
```

两条命令都应输出：

```text
True
```

如果输出 `False`，说明 PowerShell 当前不在项目根目录，请重新从项目文件夹打开终端。

## 二、安装 Python 和 Node.js

项目需要：

- Python 3.9 或更高版本，建议 Python 3.11/3.12。
- Node.js 20.19 或更高版本，建议 Node.js 22 LTS。
- npm 会随 Node.js 一起安装。

### 1. 检查是否已经安装

```powershell
py --version
node --version
npm --version
```

如果三条命令都能显示版本号，可以直接进入下一步。

如果 `py` 不存在，再尝试：

```powershell
python --version
```

只要 `py` 和 `python` 中有一个可用即可。

### 2. 使用 winget 安装

Windows 10/11 通常自带 `winget`。执行：

```powershell
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
```

安装完成后关闭当前 PowerShell，重新从项目文件夹打开 PowerShell，然后再次检查：

```powershell
py --version
node --version
npm --version
```

### 3. winget 不可用

如果提示 `winget` 不是可识别的命令，请先在 Windows 的 Microsoft Store 中安装或更新“应用安装程序”，然后重新打开 PowerShell。安装完成后仍使用上面的 `winget install` 命令。

## 三、第一次安装后端依赖

在项目根目录的 PowerShell 中执行：

```powershell
py -m venv .\backend_keep_internal\.venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\backend_keep_internal\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\backend_keep_internal\requirements.txt
```

如果电脑没有 `py` 命令，可将第一条和后面的 `py` 替换为 `python`：

```powershell
python -m venv .\backend_keep_internal\.venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\backend_keep_internal\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\backend_keep_internal\requirements.txt
```

虚拟环境激活后，PowerShell 提示符前面通常会出现 `(.venv)`。

第一次安装需要联网，看到 `Successfully installed` 后表示安装完成。

## 四、第一次安装前端依赖

保持当前 PowerShell 位于项目根目录，执行：

```powershell
npm ci
```

第一次安装需要联网。等待依赖安装完成后，项目根目录会出现 `node_modules` 文件夹。

如果 `npm ci` 失败，可以改用：

```powershell
npm install
```

## 五、第一次启动项目

项目需要两个 PowerShell 窗口：一个运行后端，一个运行前端。

### 终端一：启动后端

从项目根目录执行：

```powershell
Push-Location .\backend_keep_internal
& .\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 后表示后端启动成功。保持该窗口开启。

用浏览器检查：

<http://127.0.0.1:8000/health>

正常结果应为：

```json
{"status":"ok"}
```

### 终端二：启动前端

重新从项目根目录打开一个新的 PowerShell，执行：

```powershell
npm run dev
```

终端会显示类似：

```text
Local: http://127.0.0.1:5173/
```

使用浏览器打开该地址即可查看系统。

## 六、以后每天启动项目

环境安装完成后，不需要再次执行 `pip install` 或 `npm ci`，只需要两个终端。

### 终端一：后端

从项目根目录执行：

```powershell
Push-Location .\backend_keep_internal
& .\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 终端二：前端

从项目根目录执行：

```powershell
npm run dev
```

浏览器访问：

<http://127.0.0.1:5173/>

关闭项目时，在两个终端中分别按 `Ctrl+C`。

## 七、检查项目是否正常

后端测试：

```powershell
Push-Location .\backend_keep_internal
& .\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
Pop-Location
```

前端构建检查：

```powershell
npm run build
```

## 常见问题

### 1. 提示找不到 Python

依次尝试：

```powershell
py --version
python --version
```

如果都不存在，执行：

```powershell
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
```

安装后关闭并重新打开 PowerShell。

### 2. 提示找不到 node 或 npm

执行：

```powershell
winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
```

安装后关闭并重新打开 PowerShell，再检查：

```powershell
node --version
npm --version
```

### 3. PowerShell 禁止运行虚拟环境脚本

执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\backend_keep_internal\.venv\Scripts\Activate.ps1
```

### 4. 页面能打开，但提示数据加载失败

先确认后端终端仍在运行，然后访问：

<http://127.0.0.1:8000/health>

如果健康检查失败，重新执行后端启动命令。

### 5. 端口 8000 已被占用

临时改用 8001：

```powershell
Push-Location .\backend_keep_internal
& .\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

同时把 `vite.config.js` 中的代理地址改为：

```js
target: 'http://127.0.0.1:8001'
```

### 6. 端口 5173 已被占用

Vite 通常会自动使用下一个端口，例如 `5174`。请以终端实际显示的 `Local` 地址为准。

### 7. pip 下载很慢

可以临时使用国内镜像：

```powershell
python -m pip install -r .\backend_keep_internal\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 8. npm 下载很慢

可以临时使用国内镜像：

```powershell
npm ci --registry=https://registry.npmmirror.com
```

运行项目时必须同时启动后端和前端两个 PowerShell 窗口。只启动前端时，页面无法获取调度结果。
