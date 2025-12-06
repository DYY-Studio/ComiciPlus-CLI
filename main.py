from client import ComiciClient
from utils import getLegalPath
import typer, pathlib, time, config, zipfile
from typing import Annotated, Literal
from urllib.parse import urlsplit
from rich.console import Console
from rich.table import Table, Column
from rich.progress import track

app = typer.Typer(rich_markup_mode="markdown")
app.add_typer(config.app, name="config")
console = Console()
client = ComiciClient()

@app.command()
def sites():
    """All supported sites listed on https://comici.co.jp/business/comici-plus"""
    console.print(client.get_all_support_sites())

@app.command()
def bookshelf(
    page: int = typer.Option(0, min = 0, help="Page number when too many bookshelf items to show"),
    bookshelf_type: Literal["", "favorite", "buying", "liking"] = typer.Option("", "--type", help="== [閲覧, お気に入り, レンタル, いいね]"),
    cookies: str = typer.Option("", help="Path to your cookies.json, should use Cookie-Editor JSON format"),
):
    if cookies: 
        client.update_cookies_from_CookieEditorJson(cookies)
    results, has_next_page = client.bookshelf(
        page=page, 
        bookshelf_type=bookshelf_type
    )
    
    table = Table(
        "Series ID", 
        Column("Title", overflow="fold"), 
        "Last Updated",
        title=f"Bookshelf (Page: {page}, Type: {bookshelf_type})", 
        show_lines=True
    )
    for result in results:
        table.add_row(
            urlsplit(result.href).path.rstrip("/").split("/")[-1], 
            result.title,
            result.last_update
        )

    console.print(table)
    if has_next_page: 
        console.print(f"[yellow]There are more bookshelf items, use `--page {page+1}` to show them[/]")

@app.command()
def author(
    author_id: str,
    page: int = typer.Option(0, min = 0, help="Page number when too many series to show"),
):
    """List series of a author by author_id, only some sites support this"""
    results, has_next_page = client.author(
        author_id=author_id, 
        page=page
    )
    if not results:
        console.print("[red]No results[/]")

    table = Table(
        "Series ID", 
        Column("Title", overflow="fold"), 
        "Authors", 
        "Author IDs",
        title=f"Author Series (Author ID: {author_id}, Page: {page})", 
    )
    for result in results:
        table.add_row(
            urlsplit(result.href).path.rstrip("/").split("/")[-1], 
            result.title, 
            "\n".join([author.name for author in result.author]), 
            "\n".join([urlsplit(author.href).path.rstrip("/").split("/")[-1] for author in result.author])
        )
    
    console.print(table)
    if has_next_page: 
        console.print(f"[yellow]There are more series, use `--page {page+1}` to show them[/]")

@app.command()
def series_list(
    sort: Literal["更新順", "新作順"] = "更新順",
    page: int = typer.Option(0, min = 0, help="Page number when too many series to show"),
):
    """List all series on the site"""
    results, has_next_page = client.series_list(
        sort=sort, 
        page=page
    )
    if not results:
        console.print("[red]No results[/]")

    has_author_ids = False
    for result in results:
        for author in result.author: 
            if author.href: 
                has_author_ids = True
                break
    
    table = Table(
        "Series ID", 
        Column("Title", overflow="fold"), 
        "Authors", 
        title=f"Series List (Sort: {sort}, Page: {page})", 
        show_lines=True
    )
    if has_author_ids: 
        table.add_column("Author IDs")

    for result in results:
        cols = [
            urlsplit(result.href).path.rstrip("/").split("/")[-1], 
            result.title, 
            "\n".join([author.name for author in result.author]),
        ]
        if has_author_ids: 
            cols.append(
                "\n".join([urlsplit(author.href).path.rstrip("/").split("/")[-1] for author in result.author])
            )
            
        table.add_row(*cols)
    
    console.print(table)

    if has_next_page: 
        console.print(f"[yellow]There are more series, use `--page {page+1}` to show them[/]")

@app.command()
def search(
    keyword: str, 
    page: int = typer.Option(0, min = 0, help="Page number when too many results to show against the limit"),
    size: int = typer.Option(30, min = 0, help="Limit of results to show"),
    _filter: Literal["series", "seriesofauthors", "articles"] = typer.Option(
        "series", "--filter", help="Filter type. Articles == Episodes"
    ),
):
    results, has_next_page = client.search(
        keyword,
        page=page, 
        size=size, 
        _filter=_filter
    )
    if not results:
        console.print("[red]No results[/]")
    
    if _filter == "articles":
        table = Table(
            "Episode ID", 
            Column("Title", overflow="fold"), 
            title=f"Search Results (Filter: {_filter}, Page: {page}, Limit: {size})", 
            show_lines=True
        )
        for result in results:
            table.add_row(
                urlsplit(result.href).path.rstrip("/").split("/")[-1], 
                result.title
            )
    else:
        table = Table(
            "Series ID", 
            Column("Title", overflow="fold"), 
            "Authors", 
            title=f"Search Results (Filter: {_filter}, Page: {page}, Limit: {size})", 
            show_lines=True
        )

        has_author_ids = False
        for result in results:
            for author in result.author: 
                if author.href: 
                    has_author_ids = True
                    break
        
        if has_author_ids:
            table.add_column("Author IDs")

        for result in results:
            cols = [
                urlsplit(result.href).path.rstrip("/").split("/")[-1], 
                result.title, 
                "\n".join([author.name for author in result.author]),
            ]
            if has_author_ids: 
                cols.append(
                    "\n".join([urlsplit(author.href).path.rstrip("/").split("/")[-1] for author in result.author])
                )
            table.add_row(
                *cols
            )
    console.print(table)

    if has_next_page: 
        console.print(f"[yellow]There are more results, use `--page {page+1}` and `--size` to show more[/]")

def load_cookies(cookies: str = ""):
    global client
    if cookies: 
        cookies = pathlib.Path(cookies)
        if cookies.exists():
            client.update_cookies_from_CookieEditorJson(cookies)
            console.print(f"[green]Loaded cookies from '{cookies}'[/]")
        else: 
            console.print(f"[red]Cookies file not found: '{cookies}'[/]")
            typer.Abort()
            return

@app.command()
def episodes(
    series_id: str, 
    sort: Literal[1,2] = typer.Option(2, help="1: Newest first, 2: Oldest first"), 
    page: int = typer.Option(0, min = 0, help="Page number when too many episodes to show against the limit"), 
    limit: int = typer.Option(50, min = 0, help="Limit of episodes to show"), 
    cookies: str = typer.Option("", help="Path to your cookies.json, should use Cookie-Editor JSON format"), 
    bought_only: bool = typer.Option(True, help="Only show bought episodes"),
):
    """
    Show episodes in target series

    Series ID can be found by using `search` command
    """
    load_cookies(cookies)
    
    paging_list, has_next_page = client.series_pagingList(
        series_id=series_id,
        sort=sort, 
        page=page, 
        limit=limit
    )
    table = Table(
        "Episode ID", 
        Column("Title", overflow="fold"), 
        "Symbols", 
        "Update Date", 
        title=f"Paging List (Page {page}, Limit {limit})", 
        show_lines=True
    )
    for episode in paging_list:
        if bought_only:
            if not episode.href: continue
            elif not episode.symbols[0].split("\n")[0] in ("閲覧期限", "無料", "今なら無料"):
                continue
        table.add_row(
            urlsplit(episode.href).path.rstrip("/").split("/")[-1] if episode.href else "-", 
            episode.title, 
            ", ".join(episode.symbols), 
            episode.update_date, 
        )
    console.print(table)
    if has_next_page: 
        console.print(f"[yellow]There are more episodes, use `--page {page+1}` and `--limit` to show more[/]")

@app.command("detailed-episodes")
def detailed_episodes(episode_id: str):
    """
    Show detailed info of all episodes in the series, but need one of episode_id to request
    """
    comici_viewer_id = client.episodes(episode_id=episode_id)
    if not comici_viewer_id: 
        console.print(f"[red]Cannot access episode {episode_id}[/]")
        typer.Abort()
        return
    book_info = client.book_info(comici_viewer_id)
    episode_info = client.book_episodeInfo(comici_viewer_id)

    table = Table(
        "Comici Viewer ID", 
        Column("Title", overflow="fold"), 
        Column("Description", overflow="fold"), 
        "Pages", 
        "No.", 
        "Publish Date", 
        "End Date", 
        title=f"Episodes Info of {book_info.title}", 
        show_lines=True
    )
    for episode in episode_info:
        publish_date = episode.publish_date.astimezone().strftime("%Y/%m/%d %H:%M:%S")
        end_date = episode.end_date.astimezone().strftime("%Y/%m/%d %H:%M:%S") if episode.end_date.year < 9999 else "N/A"
        table.add_row(
            episode._id, 
            episode.name, 
            episode.description, 
            episode.page_count, 
            episode.episode_number, 
            publish_date, 
            end_date, 
        )
    console.print(table)

@app.command("download-episode")
def download_episode(
    episode_id: str = typer.Argument(help="Episode ID (13 chars) / Comici Viewer ID (32 chars) / full URL of episode"), 
    cookies: str = "", 
    page_from: int = 0, 
    page_to: int = -1,
    save_dir: str = "",
    cbz: bool = typer.Option(False, help="Save as CBZ file"),
    overwrite: bool = typer.Option(False, help="Overwrite existing files"),
    wait_interval: float = typer.Option(0.5, min = 0, help="Wait interval between each page download"),
    ls_webp: bool = typer.Option(False, help="Use lossless WebP instead of PNG"),
    compression: int = typer.Option(1, min = 0, max = 9, help="Compression level, PNG max: 9, WebP max: 6"),
):
    load_cookies(cookies)

    if len(episode_id) not in (13, 32):
        if urlsplit(client.HOST).hostname in urlsplit(episode_id).hostname:
            episode_id = urlsplit(episode_id).path.rstrip("/").split("/")[-1]
        else:
            console.print("[red]Invalid series ID[/]")
            typer.Abort()
            return
    
    if len(episode_id) == 13:
        comici_viewer_id = client.episodes(episode_id=episode_id)
        if not comici_viewer_id: 
            console.print(f"[red]Cannot access episode {episode_id}[/]")
            typer.Abort()
            return
        console.print(f"[green]Detected Episode ID: '{episode_id}'[/]")
    else:
        comici_viewer_id = episode_id
        console.print(f"[green]Detected Comici Viewer ID: '{episode_id}'[/]")
    episodes_info = client.book_episodeInfo(comici_viewer_id)
    book_info = client.book_info(comici_viewer_id)

    episode_infos = [episode for episode in episodes_info if episode._id == comici_viewer_id]
    if not episode_infos: 
        console.print("[red]Episode not found[/]")
        typer.Abort()
        return
    
    episode_info = episode_infos[0]

    page_to = int(episode_info.page_count) if page_to < 0 or page_to > int(episode_info.page_count) else page_to
    page_from = 0 if page_from < 0 or page_from > page_to else page_from

    contents_info = client.book_contentsInfo(
        comici_viewer_id, 
        page_from, 
        page_to, 
        client.user_id if client.user_id else "0"
    )

    save_dir_path = pathlib.Path(save_dir)
    save_dir_path = save_dir_path / getLegalPath(book_info.title) / getLegalPath(episode_info.name)
    save_dir_path.mkdir(parents=True, exist_ok=True)

    filename_just = len(str(page_to)) + 1

    console.print(f"[green] Downloading episode '{episode_info.name}' of '{book_info.title}'[/]")

    if cbz:
        cbz_file_path = save_dir_path.parent / f"{getLegalPath(episode_info.name)}.cbz"
        cbz_file = zipfile.ZipFile(
            str(cbz_file_path),
            "a" if cbz_file_path.exists() else "w"
        )

    for contents in track(contents_info):
        filename = "{}.{}".format(
            str(contents.sort + 1).rjust(filename_just, '0'),
            "webp" if ls_webp else "png"
        )

        save_full_path = save_dir_path / filename
        if save_full_path.exists():
            if cbz:
                if cbz_file.mode == "a":
                    if filename in cbz_file.namelist(): continue
                cbz_file.write(save_full_path, filename)
                save_full_path.unlink(missing_ok=True)
                continue
            if not overwrite: continue
        else:
            if cbz and cbz_file.mode == "a" and filename in cbz_file.namelist(): continue

        image = client.get_and_descramble_image(contents, episode_id)
        if cbz:
            with cbz_file.open(filename, "w") as f:
                if ls_webp:
                    image.save(f, "WEBP", lossless=True, method=compression if compression <= 6 else 6)
                else:
                    image.save(f, "PNG", compress_level=compression)
        else:
            if ls_webp:
                image.save(save_full_path, "WEBP", lossless=True, method=compression if compression <= 6 else 6)
            else:
                image.save(save_full_path, "PNG", compress_level=compression)
        time.sleep(wait_interval)

    if cbz:
        cbz_file.close()
        if save_dir_path.exists(): 
            try:
                save_dir_path.rmdir()
            except:
                pass
        console.print(f"[green] Downloaded {page_to - page_from + 1} pages to '{cbz_file_path}'[/]")
    else:
        console.print(f"[green] Downloaded {page_to - page_from + 1} pages to '{save_dir_path}'[/]")

@app.command("download-series")
def download_series(
    series_id: str = typer.Argument(help="Series ID (13 chars) / full URL of series"), 
    cookies: str = "",
    save_dir: str = "",
    cbz: bool = typer.Option(False, help="Save as CBZ file"),
    overwrite: bool = typer.Option(False, help="Overwrite existing files"),
    wait_interval: float = typer.Option(0.5, min = 0, help="Wait interval between each page download"),
    ls_webp: bool = typer.Option(False, help="Use lossless WebP instead of PNG"),
    compression: int = typer.Option(1, min = 0, max = 9, help="Compression level, PNG max: 9, WebP max: 6"),
):
    load_cookies(cookies)

    if len(series_id) != 13:
        if urlsplit(client.HOST).hostname in urlsplit(series_id).hostname:
            series_id = urlsplit(series_id).path.rstrip("/").split("/")[-1]
        else:
            if urlsplit(client.HOST).hostname not in urlsplit(series_id).hostname:
                console.print(f"[red]Invalid series ID: Hostname mismatch[/]")
            else:
                console.print("[red]Invalid series ID[/]")
            typer.Abort()
            return

    console.print(f"[green]Downloading series '{series_id}'[/]")

    page = 0
    paging_list, has_next_page = client.series_pagingList(
        series_id=series_id,
    )

    while has_next_page:
        page += 1
        paging_list_cache, has_next_page = client.series_pagingList(
            series_id=series_id,
            page=page,
        )
        paging_list.extend(paging_list_cache)

    console.print(f"[green] Found {len(paging_list)} episodes[/]")

    for episode in paging_list:
        if episode.href and episode.symbols[0].split("\n")[0] in ("閲覧期限", "無料", "今なら無料"):
            download_episode(
                episode_id=urlsplit(episode.href).path.rstrip("/").split("/")[-1],
                save_dir=save_dir,
                cbz=cbz,
                ls_webp=ls_webp,
                compression=compression,
                wait_interval=wait_interval,
                overwrite = overwrite
            )
        else:
            console.print(f"[yellow] Episode '{episode.title}' is not available for your account[/]")

if __name__ == "__main__":
    app()