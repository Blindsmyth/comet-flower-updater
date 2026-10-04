import click
from pathlib import Path
from .parser import parse_zd2

@click.group()
def main() -> None:
    """Tooling for Zoom .ZD2 patch files."""
    pass

@main.command()
@click.argument('file_path', type=click.Path(exists=True))
def inspect(file_path: str) -> None:
    """Inspect a .ZD2 file and print its header and blocks."""
    path = Path(file_path)
    with path.open('rb') as f:
        data = f.read()
    
    try:
        patch = parse_zd2(data)
        
        click.echo(f"File: {path.name}")
        click.echo("-" * 40)
        click.echo(f"Magic:        {patch.header.magic}")
        click.echo(f"Checksum:     0x{patch.header.checksum:08X}")
        click.echo(f"Version:      {patch.header.version}")
        click.echo(f"Group ID:     {patch.header.group_id}")
        click.echo(f"Effect ID:    0x{patch.header.effect_id:08X}")
        click.echo(f"Effect Name:  {patch.header.name}")
        click.echo(f"Group Name:   {patch.header.group_name}")
        click.echo("-" * 40)
        click.echo(f"Blocks found: {len(patch.blocks)}")
        for i, block in enumerate(patch.blocks):
            click.echo(f"  {i+1}. {block.tag} ({block.length} bytes)")
            
    except Exception as e:
        click.echo(f"Error parsing file: {e}", err=True)

@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--out-dir', '-o', default='extracted', help='Directory to save blocks')
def extract(file_path: str, out_dir: str) -> None:
    """Extract all blocks from a .ZD2 file as individual files."""
    path = Path(file_path)
    with path.open('rb') as f:
        data = f.read()
    
    try:
        patch = parse_zd2(data)
        out_path = Path(out_dir) / path.stem
        out_path.mkdir(parents=True, exist_ok=True)
        
        click.echo(f"Extracting blocks to {out_path}...")
        
        for block in patch.blocks:
            ext = ".bin"
            if block.tag in ["PRMJ", "TXE1", "TXJ1"]:
                ext = ".txt"
            elif block.tag == "DATA":
                ext = ".elf"
            
            block_file = out_path / f"{block.tag}{ext}"
            with block_file.open('wb') as f_out:
                f_out.write(block.data)
            click.echo(f"  - Saved {block.tag}{ext}")
            
    except Exception as e:
        click.echo(f"Error extracting blocks: {e}", err=True)

if __name__ == '__main__':
    main()
