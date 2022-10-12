"""pan_deduper.sec_cli"""
import asyncio
import platform
import sys
from typing import Optional

import typer

from pan_deduper.utils import run_secduper

app = typer.Typer(
    name="secduper",
    add_completion=False,
    help="PA Security Rules deduper",
)

# friggin windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@app.command("xml", help="Gather Security Rules via XML")
def xml(
    filename: Optional[str] = typer.Option(
        None,
        "--filename",
        "-f",
        prompt="XML FIlename: ",
    )
) -> None:
    """
    Command Line Entry via XML

    Args:
        filename: filename.xml
    """
    print("\n\tXML Time!\n")
    try:
        with open(filename, encoding="utf8") as f:
            configstr = f.read()
    except OSError as e:
        print(e)
        print("\nFile open failed...typo?\n")
        sys.exit(1)

    print("Not yet implemented, sorry!")
    sys.exit()


@app.command("panorama", help="Gather Security Rules via Panorama")
def panorama(
    panorama_ip: Optional[str] = typer.Option(
        None,
        "--ip",
        "-i",
        prompt="Panorama IP/FQDN: ",
        help="Panorama IP/FQDN",
        metavar="x.x.x.x or abc.xyz.com",
    ),
    username: Optional[str] = typer.Option(
        None, "--username", "-u", prompt="Panorama Username: "
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        prompt="Panorama Password: ",
        hide_input=True,
    ),
) -> None:
    """
    Command Line Entry via Panorama

    Args:
        panorama_ip: ip/fqdn of panorama
        username:
        password:
    """
    print("\n\tPanorama Time!\n")
    asyncio.run(
        run_secduper(panorama=panorama_ip, username=username, password=password)
    )
