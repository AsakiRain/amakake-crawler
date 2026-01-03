# amakake-crawler

用于抓取 https://amakake-plant.jimdofree.com/ 并进行静态化保存的脚本。通过浏览器渲染页面，解析 DOM，下载页面内资源并改写引用，从而生成可离线浏览的站点副本。

## 功能
- 使用 DrissionPage 打开页面，支持动态渲染内容。
- 解析页面 DOM，下载图片、脚本、CSS、字体等资源到本地。
- 处理内联样式、<style> 块、外链 CSS 中的 url() 和 @import 资源，递归下载并改写路径。
- 处理 Jimdo 的 jimdoData 配置中的图片资源并本地化。
- 改写站内链接为本地 html 文件名，站外链接加上 target="_blank"。
- 保存每个页面为 html 文件，并输出到本地目录。

## 依赖
- Python 3.10+
- DrissionPage
- beautifulsoup4

## 使用方法
1. 安装依赖：
   - 如果使用 uv：`uv sync`
   - 或者用 pip 安装 `DrissionPage` 和 `beautifulsoup4`
2. 运行脚本：`python save_site.py`
3. 浏览器打开页面后，等待页面完全加载，按 Enter 继续抓取。
4. 脚本会自动发现站内链接并依次抓取。

## 输出结构
- 页面文件输出到 `Amakake_Complete_Local/`
- 资源文件输出到 `Amakake_Complete_Local/assets/`

## 重要说明
- 抓取时需要人工确认页面加载完成（按 Enter）。
- 仅抓取站内链接，且会跳过登录、购物车等路径。
- 资源文件名使用 URL 的 MD5 生成，避免重复与冲突。

## 配置
在 `save_site.py` 顶部可以修改：
- `START_URL`：起始网址
- `SAVE_DIR`：保存目录
- `ASSET_DIR_NAME`：资源目录名
