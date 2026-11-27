"""
一次性脚本：把 Google Fonts (Cinzel/Cinzel Decorative/Cormorant Garamond) 三个字体
+ FontAwesome 6.4.0 下载到 static/vendor/，下载后即可断网使用。

源：fonts.googleapis.cn（Google 中国官方镜像，断网场景下唯一可用源）
"""
import os
import re
import urllib.request
import urllib.error
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, 'static', 'vendor')
FONTS_DIR = os.path.join(VENDOR, 'fonts')
FA_DIR = os.path.join(VENDOR, 'fontawesome')

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'}


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout)


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        if hasattr(data, 'read'):
            data = data.read()
        f.write(data)
    return len(data) if hasattr(data, '__len__') else 0


def download_google_fonts():
    """下载三个字体文件的 woff2（用 modern 浏览器 UA 拿到 woff2 链接）"""
    # 完整 url（含所有字重 + italic）
    css_url = (
        'https://fonts.googleapis.cn/css2?'
        'family=Cinzel+Decorative:wght@400;700&'
        'family=Cinzel:wght@400;500;600;700&'
        'family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&'
        'display=swap'
    )
    print(f'[google-fonts] GET {css_url}')
    css = fetch(css_url).read().decode('utf-8')

    # 不写 css 文件本身（断网时浏览器不需要），只抽 woff2 url 下载
    # 抽取每个 @font-face 块
    blocks = re.findall(
        r'@font-face\s*\{[^}]*?font-family:\s*\'(?P<fam>[^\']+)\'[^}]*?'
        r'font-style:\s*(?P<style>\w+)[^}]*?'
        r'font-weight:\s*(?P<weight>\d+)[^}]*?'
        r'src:\s*url\((?P<url>[^)]+)\)[^}]*?\}',
        css, re.DOTALL
    )
    if not blocks:
        # 备用策略：直接抓所有 url()
        urls = re.findall(r'url\((https?://[^)]+\.woff2)\)', css)
        print(f'[google-fonts] 备用抓 url: {len(urls)} 个')
        for u in urls:
            download_font_file(u)
        return

    for fam, style, weight, url in blocks:
        # 用 family 中文标识 + 权重 + style 命名
        slug = fam.lower().replace(' ', '-')
        style_slug = 'italic' if style == 'italic' else 'normal'
        filename = f'{slug}-{weight}-{style_slug}.woff2'
        out = os.path.join(FONTS_DIR, filename)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            print(f'  [SKIP] {filename} (exists, {os.path.getsize(out)} bytes)')
            continue
        print(f'  [GET]   {fam}/{weight}/{style} -> {url}')
        download_font_file(url, filename_hint=filename)


def download_font_file(url, filename_hint=None):
    try:
        data = fetch(url).read()
        if filename_hint is None:
            filename_hint = os.path.basename(url.split('?')[0])
        out = os.path.join(FONTS_DIR, filename_hint)
        save(out, data)
        print(f'    [OK] {filename_hint}: {len(data)} bytes')
    except Exception as e:
        print(f'    [FAIL] {url}: {e}', file=sys.stderr)


def download_fontawesome():
    """下载 FontAwesome 6.4.0 free CSS + webfonts"""
    # 镜像：jsdelivr.net 通常可达
    mirrors = [
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css',
         'all.min.css'),
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/webfonts/fa-regular-400.woff2',
         'webfonts/fa-regular-400.woff2'),
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/webfonts/fa-solid-900.woff2',
         'webfonts/fa-solid-900.woff2'),
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/webfonts/fa-brands-400.woff2',
         'webfonts/fa-brands-400.woff2'),
    ]
    for url, rel in mirrors:
        out = os.path.join(FA_DIR, rel)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            print(f'  [SKIP] fa/{rel} (exists)')
            continue
        try:
            # 如果 CSS 内引用的 webfonts 路径是相对的 ../webfonts/，需要替换
            data = fetch(url).read()
            save(out, data)
            print(f'  [OK]   fa/{rel}: {len(data)} bytes')
        except Exception as e:
            print(f'  [FAIL] fa/{rel}: {e}', file=sys.stderr)


def post_process_fa_css():
    """把 CSS 内 webfonts url() 改成相对路径 ../webfonts/ 同目录"""
    css_path = os.path.join(FA_DIR, 'all.min.css')
    if not os.path.exists(css_path):
        print('[fa] no css to post-process')
        return
    with open(css_path, 'r', encoding='utf-8') as f:
        css = f.read()
    # jsdelivr 的 CSS 内 url 是 ../webfonts/xxx.woff2，但相对 css 文件位置
    # （static/vendor/fontawesome/all.min.css）需要改成 webfonts/xxx.woff2
    css = css.replace('url(../webfonts/', 'url(webfonts/')
    # 替换可能的 https:// 绝对 url（jsdelivr CDN 残留）为本地
    css = re.sub(r'url\((https?:)?//[^)]+\)', lambda m: f'url({m.group(0)[4:]})', css)
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css)
    print(f'[fa] css post-processed: path rewrite done')


def main():
    os.makedirs(FONTS_DIR, exist_ok=True)
    os.makedirs(FA_DIR, exist_ok=True)
    print('=== vendor-localize 一次性下载脚本 ===')
    print(f'vendor: {VENDOR}')
    print()
    print('--- Google Fonts ---')
    download_google_fonts()
    print()
    print('--- FontAwesome 6.4.0 ---')
    download_fontawesome()
    post_process_fa_css()
    print()
    print('完成。')

if __name__ == '__main__':
    main()
