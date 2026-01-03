from DrissionPage import ChromiumPage, ChromiumOptions
from bs4 import BeautifulSoup
import os
import time
import requests
import hashlib
import re
import html
import json
from datetime import datetime
from urllib.parse import urlparse, urljoin, unquote

# ================= 配置区 =================
START_URL = "https://amakake-plant.jimdofree.com/"
SAVE_DIR = "Amakake_Complete_Local"
ASSET_DIR_NAME = "assets"
# =========================================

ASSET_PATH = os.path.join(SAVE_DIR, ASSET_DIR_NAME)
if not os.path.exists(ASSET_PATH):
    os.makedirs(ASSET_PATH)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_session(page):
    s = requests.Session()
    s.headers.update({"User-Agent": page.user_agent})
    try:
        cookies = page.cookies()
        for c in cookies:
            s.cookies.set(c['name'], c['value'])
    except:
        pass
    return s

def get_safe_filename(url):
    try:
        path_part = url.split('?')[0].split('#')[0]
        ext = os.path.splitext(path_part)[1].lower()
        
        if not ext:
            if "css" in url or "font" in url and "family" in url: ext = ".css"
            elif "js" in url: ext = ".js"
            elif "png" in url: ext = ".png"
            elif "jpg" in url: ext = ".jpg"
            elif "jpeg" in url: ext = ".jpg"
            elif "gif" in url: ext = ".gif"
            elif "ico" in url: ext = ".ico"
            elif "woff2" in url: ext = ".woff2"
            elif "woff" in url: ext = ".woff"
            elif "ttf" in url: ext = ".ttf"
            elif "svg" in url: ext = ".svg"
            else: ext = ".bin"
            
        hash_name = hashlib.md5(url.encode('utf-8')).hexdigest()
        return f"{hash_name}{ext}"
    except:
        return f"unknown_{int(time.time())}.bin"

def process_css_text(session, css_text, base_url_list, tag_info="CSS"):
    if not css_text: return ""
    css_text_decoded = html.unescape(css_text)
    
    url_pattern = re.compile(r'url\((.*?)\)', re.IGNORECASE)
    
    def url_replace(match):
        raw_content = match.group(1).strip()
        clean_url = raw_content.strip('\'"').strip()
        if clean_url.startswith('data:') or not clean_url: return match.group(0)
        
        indent = "      " 
        if tag_info == "RecursiveCSS": indent = "        "
        
        # CSS 内部资源递归下载
        _, filename = download_asset(session, clean_url, base_url_list, indent, parent_type="CSS")
        
        if filename:
            if tag_info == "Inline":
                log(f"      ★ [内联修复] {clean_url} -> assets/{filename}")
            return f'url("{filename}")'
        return match.group(0)

    import_pattern = re.compile(r'@import\s+[\'"](.*?)[\'"];', re.IGNORECASE)
    def import_replace(match):
        original = match.group(1).strip()
        indent = "      "
        if tag_info == "RecursiveCSS": indent = "        "
        _, filename = download_asset(session, original, base_url_list, indent, parent_type="CSS")
        if filename:
            return f'@import "{filename}";'
        return match.group(0)

    try:
        modified = url_pattern.sub(url_replace, css_text_decoded)
        modified = import_pattern.sub(import_replace, modified)
        return modified
    except Exception as e:
        log(f"    CSS解析错误: {e}")
        return css_text

def download_asset(session, url, referer_list, indent="    ", parent_type="Asset"):
    if not url or url.startswith('data:') or url.startswith('#'): return None, None
    
    base_ref = referer_list[0] if isinstance(referer_list, list) else referer_list
    full_url = urljoin(base_ref, url)
    
    filename = get_safe_filename(full_url)
    local_path = os.path.join(ASSET_PATH, filename)
    relative_path = f"{ASSET_DIR_NAME}/{filename}"

    if os.path.exists(local_path):
        return relative_path, filename

    if not isinstance(referer_list, list):
        referer_list = [referer_list]
    referer_strategies = referer_list + [None] 

    log(f"{indent}--> [下载] {full_url}")

    for ref in referer_strategies:
        try:
            headers = {}
            if ref: headers["Referer"] = ref
            else: headers.pop("Referer", None)

            if "dlsite" in full_url: headers["Referer"] = "https://www.dlsite.com/"
            
            resp = session.get(full_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                # 递归 CSS 处理
                if filename.endswith(".css"):
                    try:
                        content_str = resp.content.decode('utf-8', errors='ignore')
                        modified_content = process_css_text(session, content_str, [full_url, base_ref], tag_info="RecursiveCSS")
                        with open(local_path, 'w', encoding='utf-8') as f:
                            f.write(modified_content)
                        log(f"{indent}    √ CSS递归完成")
                    except:
                        with open(local_path, 'wb') as f:
                            f.write(resp.content)
                else:
                    with open(local_path, 'wb') as f:
                        f.write(resp.content)
                return relative_path, filename
        except:
            pass
    
    log(f"{indent}!! [失败] {full_url}")
    return None, None

def process_jimdo_data(session, script_content, base_url_list):
    if not script_content or "jimdoData" not in script_content:
        return script_content
    
    pattern = re.compile(r'var\s+jimdoData\s*=\s*(\{.*?\});', re.DOTALL)
    match = pattern.search(script_content)
    
    if match:
        json_str = match.group(1)
        try:
            data = json.loads(json_str)
            modified = False
            
            def recursive_download(obj):
                nonlocal modified
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == "url" and isinstance(v, str) and v.startswith("http"):
                            log(f"    -> [JS数据] 配置图片: {v}")
                            _, filename = download_asset(session, v, base_url_list, indent="      ")
                            if filename:
                                obj[k] = f"{ASSET_DIR_NAME}/{filename}"
                                modified = True
                        else:
                            recursive_download(v)
                elif isinstance(obj, list):
                    for item in obj:
                        recursive_download(item)

            recursive_download(data)

            if modified:
                new_json_str = json.dumps(data, ensure_ascii=False)
                new_script_content = script_content.replace(json_str, new_json_str)
                log("    ★ jimdoData 已修正")
                return new_script_content
        except:
            pass
    
    return script_content

def download_external_css(session, url, referer):
    full_url = urljoin(referer, url)
    filename = get_safe_filename(full_url)
    local_path = os.path.join(ASSET_PATH, filename)
    relative_path = f"{ASSET_DIR_NAME}/{filename}"

    try:
        log(f"  --> [外部CSS] {full_url}")
        resp = session.get(full_url, timeout=15)
        if resp.status_code == 200:
            content = resp.content.decode('utf-8', errors='ignore')
            modified = process_css_text(session, content, [full_url, referer], tag_info="ExternalCSS")
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(modified)
            return relative_path
    except:
        pass
    return url

def clean_page_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path: return "index.html"
    name = unquote(path).replace("/", "_")
    if not name.endswith(".html"): name += ".html"
    return name

def process_page(page, session, url, visited_urls):
    log(f"分析 DOM: {url}")
    html_content = page.html
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. JimdoData (背景图配置)
    for script in soup.find_all('script'):
        if script.string and "jimdoData" in script.string:
            new_content = process_jimdo_data(session, script.string, [url, START_URL])
            script.string = new_content

    # 2. 内联样式 (style="...")
    for tag in soup.find_all(attrs={"style": True}):
        style_content = tag['style']
        if "url" in style_content.lower():
            new_style = process_css_text(session, style_content, [url, START_URL], tag_info="Inline")
            if new_style != style_content:
                tag['style'] = new_style

    # 3. 内部样式块 (<style>)
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            new_css = process_css_text(session, style_tag.string, url, tag_info="StyleBlock")
            style_tag.string.replace_with(new_css)

    # 4. Link 标签 (CSS 和 Favicon)
    for link in soup.find_all('link'):
        href = link.get('href')
        if not href: continue
        
        rel = link.get('rel', [])
        if isinstance(rel, str): rel = [rel]
        as_attr = link.get('as', '')
        
        # A. CSS
        is_css = "stylesheet" in rel or ("preload" in rel and as_attr == "style")
        if is_css:
            local_path = download_external_css(session, href, url)
            link['href'] = local_path
            if "preload" in rel:
                link['rel'] = "stylesheet"
                if link.get('as'): del link['as']
        
        # B. Favicon 【新增】
        # rel 可能是 ['shortcut', 'icon'] 或 ['icon']
        if any(r in rel for r in ['icon', 'shortcut']):
            log(f"    -> 发现 Favicon: {href}")
            path, _ = download_asset(session, href, url)
            if path: 
                link['href'] = path
                log(f"       ★ Favicon 已本地化")

    # 5. Meta 标签 (OG Image, Secure URL)
    target_props = ["og:image", "og:image:secure_url"]
    target_names = ["twitter:image"]
    
    for meta in soup.find_all('meta'):
        content = meta.get('content')
        if not content: continue
        
        prop = meta.get('property')
        name = meta.get('name')
        
        if prop in target_props or name in target_names:
            log(f"    -> Meta图片: {prop or name}")
            path, _ = download_asset(session, content, url)
            if path: meta['content'] = path

    # 6. 常规清理 (Script/IMG/JS)
    for script in soup.find_all('script'):
        if script.string and ("loadCss" in script.string or "onloadCSS" in script.string):
            script.decompose()

    for script in soup.find_all('script'):
        if script.get('src'):
            path, _ = download_asset(session, script['src'], url)
            if path: script['src'] = path

    for img in soup.find_all('img'):
        target = img.get('data-src') or img.get('src')
        if target:
            path, _ = download_asset(session, target, url)
            if path:
                img['src'] = path
                if img.get('srcset'): del img['srcset']
                if img.get('data-src'): del img['data-src']

    # 7. 链接本地化
    new_urls = []
    domain = urlparse(START_URL).netloc
    for a in soup.find_all('a'):
        href = a.get('href')
        if not href: continue
        full_href = urljoin(url, href)
        parsed = urlparse(full_href)
        
        if parsed.netloc == domain:
            if any(ext in parsed.path.lower() for ext in ['.jpg', '.zip', '.pdf', '.png']): continue 
            if any(k in parsed.path.lower() for k in ['/login', 'auth', 'cart']): continue
            
            clean = full_href.split('#')[0].split('?')[0]
            a['href'] = clean_page_filename(clean)
            if clean not in visited_urls:
                new_urls.append(clean)
        else:
            a['target'] = "_blank"

    page_filename = clean_page_filename(url)
    save_path = os.path.join(SAVE_DIR, page_filename)
    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    log(f"√ 保存完毕: {page_filename}")
    return new_urls

def main():
    co = ChromiumOptions()
    co.headless(False)
    co.ignore_certificate_errors(True)
    page = ChromiumPage(co)
    
    to_visit = [START_URL]
    visited = set()
    
    try:
        while to_visit:
            current_url = to_visit.pop(0)
            if current_url.rstrip('/') in visited: continue
            
            if current_url != page.url:
                print(f"\n正在跳转: {current_url}")
                try: page.get(current_url, retry=0, timeout=8)
                except: pass
            
            session = get_session(page)
            print("-" * 50)
            print(f"当前: {current_url}")
            input(">>> 页面完全加载后按【回车】 (Enter)...")
            
            new_links = process_page(page, session, current_url, visited)
            visited.add(current_url.rstrip('/'))
            
            for link in new_links:
                if link.rstrip('/') not in visited and link.rstrip('/') not in [u.rstrip('/') for u in to_visit]:
                    to_visit.append(link)
    except KeyboardInterrupt:
        print("\n停止")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()