# ComiciPlus-CLI
适用于所有[基于SaaS『コミチ＋』(Comici Plus) 的漫画网站](https://comici.co.jp/business/comici-plus)的CLI工具

本工具仅供个人学习交流使用，请勿用于其他用途。
# 功能
* 搜索漫画
* 查询漫画话数信息
* 下载单话 / 批量下载整个连载
* WebP / PNG 图像输出
* CBZ格式输出

*注意* 原始图像质量因提供商和作品而异，如**コミックグロウル**可以提供高达**1360x1920**的**Q98 JPEG**。

*注意* 需要从打乱图像恢复出原始图像，所以才使用无损压缩的PNG/WebP进行保存。**保存的图像并不是原图，本工具也无法获取真正的原图**。请到电子书平台购买单行本或杂志支持作者和出版社。

# 安装
推荐在venv环境下使用本工具，目前尚不支持PyPI
1. `git clone`本仓库到本地
2. `cd`到本地仓库目录
3. 创建venv环境 `python3 -m venv .venv`
4. 激活venv环境<br>Linux/macOS: `source .venv/bin/activate`
   <br>Windows CMD: `call .\.venv\Scripts\activate.bat`
5. 安装依赖 `pip install -r requirements.txt`
6. 运行 `python main.py --help` 查看帮助

# 配置网站
本工具支持所有基于Comici的漫画网站，需要各位手动设置自己想要使用的网站

* `main.py config set --host <HOST>`

例如
* `main.py config set --host https://comic-growl.com`
* `main.py config set --host comic-growl.com`

# 基本使用
* `search`
  * 查找漫画，得到Series ID (连载ID)
* `episodes`
  * 输入Series ID (连载ID)
  * 查询漫画话数信息，得到Episode ID (话ID)
* `detailed-episodes`
  * 输入连载下的任意一个可访问的Episode ID (话ID)
  * 通过API查询更详细的话数信息，得到Comici Viewer ID
* `download-episode`
  * 输入Episode ID下载单话
  * 或Comici Viewer ID
  * 或`https://<HOST>/episodes/<EPISODE_ID>`
  * **最好导入Cookies登入，以获得更全的访问权限**
* `download-series`
  * 输入Series ID下载整本漫画
  * 或`https://<HOST>/series/<SERIES_ID>`
  * **最好导入Cookies登入，以获得更全的访问权限**
* `config`
  * `set`
    * 在当前工作目录创建配置文件，并设置配置
  * `reset`
    * 删除配置文件
  * `show`
    * 显示当前配置

# 登入
本工具不提供登入功能，需要各位在浏览器手动登入后，使用*Cookie-Editor* Export为JSON，然后粘贴到一个JSON文件中

本工具仅支持*Cookie-Editor*的JSON格式文件

可以通过`--cookies`参数传入JSON文件路径，也可以通过`main.py config set --cookies`设置

# 代理
Comici提供的服务在中国大陆可以直接连接，不需要使用代理

如果实在需要，请通过`main.py config set --proxy`设置代理

# 许可证
MIT
# 依赖
* [typer](https://github.com/tiangolo/typer)
* [rich](https://github.com/Textualize/rich)
* [bs4](https://www.crummy.com/software/BeautifulSoup/bs4/)
* [httpx](https://github.com/encode/httpx)
* [pillow](https://github.com/python-pillow/Pillow)