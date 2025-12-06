from client import ComiciClient
import typer, pathlib, time, config, zipfile
from urllib.parse import urlsplit
from rich.console import Console
from rich.table import Table, Column
from rich.progress import track

app = typer.Typer(rich_markup_mode="markdown")
app.add_typer(config.app, name="config")
console = Console()
client = ComiciClient()

@app.command()
def search(
    keyword: str, 
    host: str = typer.Argument("", help="Host of any comic site powered by Comici(コミチ)")
):
    results = client.search(keyword)
    table = Table(
        "Series ID", 
        Column("Title", overflow="fold"), 
        "Authors", 
        title="Search Results", 
        show_lines=True
    )
    for result in results:
        table.add_row(
            urlsplit(result.href).path.rstrip("/").split("/")[-1], 
            result.title, 
            "\n".join(result.author)
        )
    console.print(table)

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
    sort: int = typer.Option(2, min = 1, max = 2, help="1: Newest first, 2: Oldest first"), 
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
    
    paging_list = client.series_pagingList(
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
        title="Paging List", 
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
    episode_id: str = typer.Argument(help="Episode ID (13 chars) or Comici Viewer ID (32 chars)"), 
    cookies: str = "", 
    page_from: int = 0, 
    page_to: int = -1,
    save_dir: str = "",
    cbz: bool = typer.Option(False, help="Save as CBZ file"),
    overwrite: bool = typer.Option(False, help="Overwrite existing files"),
    wait_interval: float = typer.Option(0.5, min = 0, help="Wait interval between each page download"),
    png_compression: int = typer.Option(1, min = 0, max = 9, help="PNG compression level"),
):
    load_cookies(cookies)

    if len(episode_id) not in (13, 32):
        console.print("[red]Invalid episode ID[/]")
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
    if cbz:
        save_dir_path = save_dir_path / book_info.title
    else:
        save_dir_path = save_dir_path / book_info.title / episode_info.name
    save_dir_path.mkdir(parents=True, exist_ok=True)

    filename_just = len(str(page_to)) + 1

    console.print(f"[green] Downloading episode '{episode_info.name}' of '{book_info.title}'[/]")

    if cbz:
        cbz_file = zipfile.ZipFile(save_dir_path / f"{episode_info.name}.cbz", "w")

    for contents in track(contents_info):
        filename = "{}.png".format(str(contents.sort + 1).rjust(filename_just, '0'))
        save_full_path = save_dir_path / filename

        if save_full_path.exists() and not overwrite: continue

        filebytes = client.get_and_descramble_image(contents, episode_id).tobytes(
            format = "PNG",
            compress_level = png_compression,
        )
        if cbz:
            cbz_file.writestr(filename, filebytes)
        else:
            save_full_path.write_bytes(filebytes)
        time.sleep(wait_interval)

    if cbz:
        cbz_file.close()
    
    console.print(f"[green] Downloaded {page_to - page_from + 1} pages to '{save_dir_path}'[/]")

@app.command("download-series")
def download_series(
    series_id: str, 
    cookies: str = "",
    save_dir: str = "",
    cbz: bool = typer.Option(False, help="Save as CBZ file"),
    overwrite: bool = typer.Option(False, help="Overwrite existing files"),
    wait_interval: float = typer.Option(0.5, min = 0, help="Wait interval between each page download"),
    png_compression: int = typer.Option(1, min = 0, max = 9, help="PNG compression level"),
):
    load_cookies(cookies)

    console.print(f"[green]Downloading series '{series_id}'[/]")

    page = 0
    paging_list = client.series_pagingList(
        series_id=series_id,
    )
    resultCount = len(paging_list)

    while resultCount > 0:
        page += 1
        paging_list_cache = client.series_pagingList(
            series_id=series_id,
            page=page,
        )
        resultCount = len(paging_list_cache)
        paging_list.extend(paging_list_cache)

    console.print(f"[green] Found {len(paging_list)} episodes[/]")

    for episode in paging_list:
        if episode.href and episode.symbols[0].split("\n")[0] in ("閲覧期限", "無料", "今なら無料"):
            download_episode(
                episode_id=urlsplit(episode.href).path.rstrip("/").split("/")[-1],
                save_dir=save_dir,
                cbz=cbz,
                png_compression=png_compression,
                wait_interval=wait_interval,
                overwrite = overwrite
            )
        else:
            console.print(f"[yellow] Episode '{episode.title}' is not available for your account[/]")

if __name__ == "__main__":
    app()