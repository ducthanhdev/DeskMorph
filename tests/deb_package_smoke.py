#!/usr/bin/python3
"""Install/reinstall/remove an authored .deb under an isolated dpkg root.

Requires bwrap user namespaces; never invokes the host's dpkg database. Runtime
libraries and dependency status are borrowed from the host, so this is not a
clean OS/account installation certification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf


def run(package, output, prior_package=None):
    package = package.resolve()
    assert package.is_file() and package.suffix == '.deb'
    output = output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
    def call(*args):
        try: return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            print(error.output, flush=True); raise
    name = call('dpkg-deb', '-f', str(package), 'Package').strip()
    assert name == 'desk-morph', name
    version = call('dpkg-deb', '-f', str(package), 'Version').strip()
    with tempfile.TemporaryDirectory(prefix='deskmorph-package-test-') as directory:
        root = Path(directory); install = root / 'root'; install.mkdir()
        control = root / 'control'
        subprocess.run(['dpkg-deb', '-e', str(package), str(control)], check=True)
        assert {p.name for p in control.iterdir()} <= {'control', 'md5sums'}, 'Inspect package maintainer scripts before running them'
        dpkg = install / 'var/lib/dpkg'
        (dpkg / 'updates').mkdir(parents=True); (dpkg / 'info').mkdir()
        # Dependency resolution uses installed host packages. All writes are
        # directed to the copied database and private install tree.
        shutil.copyfile('/var/lib/dpkg/status', dpkg / 'status')
        for file in Path('/var/lib/dpkg/info').glob('*.list'):
            shutil.copyfile(file, dpkg / 'info' / file.name)
        config = install / 'profile/com.ducthanhdev.deskmorph/config.json'
        config.parent.mkdir(parents=True)
        fixture = b'{"schemaVersion":1,"revision":17,"config":{"language":"vi","pinnedApps":[]}}\n'
        config.write_bytes(fixture)
        if prior_package:
            prior_package = prior_package.resolve()
            assert prior_package.is_file() and prior_package != package
            prior_version = call('dpkg-deb', '-f', str(prior_package), 'Version').strip()
            prior_deb = prior_package
            predecessor_sha256 = hashlib.sha256(prior_package.read_bytes()).hexdigest()
        else:
            # Keep the old fallback for package-only smoke runs. It is clearly
            # labelled synthetic and must not be used as release migration proof.
            prior = root / 'prior'
            subprocess.run(['dpkg-deb', '-R', str(package), str(prior)], check=True)
            prior_control = prior / 'DEBIAN/control'
            prior_version = version + '~package-test'
            prior_control.write_text(prior_control.read_text().replace('Version: ' + version + '\n', 'Version: ' + prior_version + '\n'))
            subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(prior), str(root / 'prior.deb')], check=True, stdout=subprocess.PIPE)
            prior_deb = root / 'prior.deb'
            predecessor_sha256 = hashlib.sha256(prior_deb.read_bytes()).hexdigest()
        sandbox = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--unshare-user', '--uid', '0', '--gid', '0', '--unshare-pid', '--unshare-net', '--proc', '/proc', '--tmpfs', '/tmp', '--bind', str(root), '/tmp/pkg-lab', '--ro-bind', str(package), '/tmp/input.deb', '--chdir', '/tmp/pkg-lab']
        def command(*args): return call(*sandbox, *args)
        def manage(*args): return command('/usr/bin/dpkg', '--root=/tmp/pkg-lab/root', '--log=/tmp/pkg-lab/dpkg.log', *args)
        if prior_package:
            shutil.copyfile(prior_package, root / 'prior.deb')
        log = [manage('--install', '/tmp/pkg-lab/prior.deb')]
        assert config.read_bytes() == fixture
        log.append(manage('--install', '/tmp/input.deb'))
        binary = install / 'usr/bin/deskmorph'
        assert binary.is_file()
        status = command('/usr/bin/dpkg-query', '--admindir=/tmp/pkg-lab/root/var/lib/dpkg', '-W', '-f=${Status} ${Version}', name)
        assert status.strip() == 'install ok installed ' + version, status
        desktop = install / 'usr/share/applications/DeskMorph.desktop'
        subprocess.run(['desktop-file-validate', str(desktop)], check=True)
        text = desktop.read_text(); assert 'deskmorph --launcher' in text and 'Icon=deskmorph' in text
        icons = list((install / 'usr/share/icons/hicolor').glob('*/apps/deskmorph.png'))
        assert len(icons) >= 3 and all(p.stat().st_size > 0 for p in icons)
        icon_sizes = []
        for icon in icons:
            image = GdkPixbuf.Pixbuf.new_from_file(str(icon))
            assert image.get_width() > 0 and image.get_width() == image.get_height()
            icon_sizes.append(dict(path=str(icon.relative_to(install)), width=image.get_width(), height=image.get_height()))
        help_text = command('/tmp/pkg-lab/root/usr/bin/deskmorph', '--help')
        assert '--launcher' in help_text
        binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
        assert config.read_bytes() == fixture
        log.append(manage('--install', '/tmp/input.deb'))
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == binary_hash and config.read_bytes() == fixture
        log.append(manage('--remove', name))
        assert not binary.exists() and not desktop.exists() and all(not p.exists() for p in icons)
        assert config.read_bytes() == fixture, 'Removal deleted user data'
        log.append(manage('--purge', name))
        assert config.read_bytes() == fixture, 'Purge deleted user data'
        report = dict(package=name, version=version, sha256=hashlib.sha256(package.read_bytes()).hexdigest(), bytes=package.stat().st_size,
            packageControl=(control / 'control').read_text(), noMaintainerScripts=True, installedStatus=status.strip(), nativeHelp=True,
            desktopValidated=True, launcherDesktopAction=True, iconFiles=len(icons), reinstallSameVersionPreservesConfig=True,
            decodedIcons=icon_sizes,
            predecessorVersion=prior_version, predecessorSha256=predecessor_sha256,
            predecessorUpgradePreservesConfig=True,
            removeDeletesPackagedFiles=True, purgePreservesUserData=True, installedBinarySha256=binary_hash,
            hostDpkgStatusUnchanged=hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest() == before,
            scope='Private dpkg root in bwrap user/PID/network namespaces; borrowed host runtime/dependency status. A real predecessor package may be supplied; without --prior-package the upgrade is synthetic and not migration proof. GUI/autostart/clean account require the separate lab.')
        assert report['hostDpkgStatusUnchanged']
        output.with_suffix('.log').write_text('\n'.join(log))
        output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path); parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--prior-package', type=Path, help='Use a real predecessor .deb instead of the synthetic fallback')
    args = parser.parse_args(); run(args.package, args.output, args.prior_package)
