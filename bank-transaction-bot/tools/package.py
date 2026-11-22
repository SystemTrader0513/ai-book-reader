"""Build a portable archive with an explicit allowlist (no .env, Git or caches)."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('app','static','config','ontology','mappings','rules','policies','templates',
               'tools','tests','docs','card-transaction-investigation')


def build():
    archive = ROOT/'dist'/'trace-card-bot.zip'
    archive.parent.mkdir(exist_ok=True)
    paths = [ROOT/name for name in ('README.md','run.sh','.gitignore')]
    for directory in SOURCE_DIRS:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix in ('.py','.md','.json','.ttl','.html','.css','.js','.txt','.jpg','.png'))
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as package:
        for path in sorted(paths):
            package.write(path,'trace-card-bot/'+str(path.relative_to(ROOT)))
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise ValueError('Invalid archive')
    return archive,len(paths)


if __name__=='__main__':
    archive,count = build()
    print('Packaged %s files: %s' % (count,archive))
