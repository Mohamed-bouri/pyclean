#!/usr/bin/env python3
"""
PyClean - Custom File Deletion Utility
Interactive command-line tool for safe, targeted file and folder cleanup.
By M-Bouri
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import uuid
from datetime import datetime
from pathlib import Path

__author__ = "M-Bouri"

BANNER = r"""
 ___           ___    _                        
(  _`\        (  _`\ (_ )                      
| |_) ) _   _ | ( (_) | |    __     _ _   ___  
| ,__/'( ) ( )| |  _  | |  /'__`\ /'_` )/' _ `\
| |    | (_) || (_( ) | | (  ___/( (_| || ( ) |
(_)    `\__, |(____/'(___)`\____)`\__,_)(_) (_)
       ( )_| |                                 
       `\___/'                      By M-Bouri            
                                         
"""

TRASH_DIRNAME = ".pyclean_trash"
LOG_FILENAME = "pyclean_log.txt"
MANIFEST_FILENAME = ".manifest.tsv"


class PyCleaner:
    def __init__(self, target_dir: str = "."):
        resolved = Path(target_dir).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            print(f" ⚠️  Path '{target_dir}' does not exist, using the current directory instead.")
            resolved = Path(".").resolve()
        self.target_dir = resolved
        self.dry_run = True  # safe preview mode by default
        self._active_batch: Path | None = None
        self._last_batch_for_restore: Path | None = None

    # ------------------------------------------------------------------ #
    # Small helpers
    # ------------------------------------------------------------------ #

    def _rel(self, p: Path) -> str:
        """Path relative to target_dir for display, falling back to the name."""
        try:
            return str(p.relative_to(self.target_dir))
        except ValueError:
            return p.name

    def _trash_root(self) -> Path:
        return self.target_dir / TRASH_DIRNAME

    def _log(self, action: str, target: str, result: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.target_dir / LOG_FILENAME, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {action} | {target} | {result}\n")
        except OSError:
            pass  # a logging failure should never crash the tool

    def _confirm(self, message: str) -> bool:
        try:
            answer = input(f"{message} (yes/no) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[cancelled] Operation cancelled.")
            return False
        return answer in ("y", "yes")

    def _iter_files(self, recursive: bool):
        """Yield files/symlinks under target_dir, always skipping the trash bin and log."""
        trash_root = self._trash_root()
        it = self.target_dir.rglob("*") if recursive else self.target_dir.iterdir()
        for item in it:
            if item == trash_root or trash_root in item.parents:
                continue
            if item.name == LOG_FILENAME:
                continue
            if item.is_file() or item.is_symlink():
                yield item

    @staticmethod
    def _extract_recursive_flag(args: list[str]) -> tuple[list[str], bool]:
        recursive = False
        clean = []
        for a in args:
            if a in ("-r", "--recursive"):
                recursive = True
            else:
                clean.append(a)
        return clean, recursive

    # ------------------------------------------------------------------ #
    # Trash (soft-delete) mechanics
    # ------------------------------------------------------------------ #

    def _begin_batch(self) -> None:
        self._active_batch = None  # created lazily on first real move

    def _end_batch(self) -> None:
        if self._active_batch is not None:
            try:
                has_content = any(self._active_batch.iterdir())
            except OSError:
                has_content = False
            if has_content:
                self._last_batch_for_restore = self._active_batch
            else:
                try:
                    self._active_batch.rmdir()
                except OSError:
                    pass
        self._active_batch = None

    def _current_trash_batch(self) -> Path:
        if self._active_batch is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            batch_dir = self._trash_root() / ts
            batch_dir.mkdir(parents=True, exist_ok=True)
            self._active_batch = batch_dir
        return self._active_batch

    def _stage_item(self, path: Path) -> bool:
        """Preview (dry-run) or move a single item into the trash bin."""
        rel_display = self._rel(path)

        if self.dry_run:
            print(f" [preview] {rel_display}")
            return False

        batch = self._current_trash_batch()
        safe_name = f"{uuid.uuid4().hex[:8]}_{path.name}"
        dest = batch / safe_name

        try:
            shutil.move(str(path), str(dest))
        except Exception as e:
            print(f" [error] could not move {rel_display}: {e}")
            self._log("DELETE_FAILED", rel_display, str(e))
            return False

        try:
            with open(batch / MANIFEST_FILENAME, "a", encoding="utf-8") as mf:
                mf.write(f"{safe_name}\t{path}\n")
        except OSError:
            pass

        print(f" [moved to trash] {rel_display}")
        self._log("DELETE", rel_display, f"{TRASH_DIRNAME}/{batch.name}/{safe_name}")
        return True

    def _process_matches(self, matches: list[Path]) -> None:
        """Shared list -> confirm -> stage pipeline used by every delete command."""
        if not matches:
            print(" No matching items found.")
            return

        for m in matches:
            tag = " [preview]" if self.dry_run else ""
            print(f"{tag} {self._rel(m)}")
        print(f" Total matching items: {len(matches)}")

        if self.dry_run:
            print(" (Preview mode is on - nothing was moved. Type 'dryrun' to switch to real mode)")
            return

        if not self._confirm(f" Move these {len(matches)} item(s) to the trash bin?"):
            print(" Operation cancelled.")
            return

        self._begin_batch()
        moved = 0
        for m in matches:
            if self._stage_item(m):
                moved += 1
        self._end_batch()
        print(f" Moved {moved}/{len(matches)} item(s) to the trash bin ({TRASH_DIRNAME}).")

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #

    def print_help(self):
        print("""
======================================================================
                          AVAILABLE COMMANDS
======================================================================
  help                     : Show this help list.
  prefix <text> [-r]       : Files starting with <text>. Add -r to also
                             search subdirectories.
  suffix <text> [-r]       : Files ending with <text> (before the extension).
  ext <ext1> <ext2>.. [-r] : Files with the given extensions
                             (example: ext jpg mp4 -r).
  empty                    : Find empty folders (including nested ones).
  batch <file1> <file2>..  : A specific list of file/folder names or paths.
  ----------------------------------------------------------------------
  trash                    : Show what's currently in the trash bin.
  restore                  : Restore the most recent trash batch.
  purge                    : Permanently empty the trash bin (cannot be undone!).
  ----------------------------------------------------------------------
  dryrun                   : Toggle between preview mode and real mode.
  dir <path>               : Change the current working directory.
  exit / quit              : Exit the program.
======================================================================
 Note: in real mode, nothing is deleted immediately or permanently.
 Every item is moved to a local trash bin (.pyclean_trash) - the most
 recent batch can be restored with 'restore'. Permanent, irreversible
 deletion only happens when you use the 'purge' command.
======================================================================
""")

    def delete_by_prefix(self, prefix: str, recursive: bool = False):
        scope = "current directory and all subdirectories" if recursive else "current directory only"
        print(f"\n Searching for files starting with '{prefix}' ({scope})...")
        matches = [f for f in self._iter_files(recursive) if f.name.startswith(prefix)]
        self._process_matches(matches)

    def delete_by_suffix(self, suffix: str, recursive: bool = False):
        scope = "current directory and all subdirectories" if recursive else "current directory only"
        print(f"\n Searching for files ending with '{suffix}' (before the extension) ({scope})...")
        matches = [f for f in self._iter_files(recursive) if f.stem.endswith(suffix)]
        self._process_matches(matches)

    def delete_by_extensions(self, extensions: list[str], recursive: bool = False):
        clean_exts = {ext.strip().lstrip('.').lower() for ext in extensions}
        scope = "current directory and all subdirectories" if recursive else "current directory only"
        print(f"\n Searching for files with extension(s): {clean_exts} ({scope})...")
        matches = [f for f in self._iter_files(recursive) if f.suffix.lstrip('.').lower() in clean_exts]
        self._process_matches(matches)

    def delete_empty_folders(self):
        trash_root = self._trash_root()

        def _empty_dirs():
            for item in sorted(self.target_dir.glob("**/*"), reverse=True):
                if item == trash_root or trash_root in item.parents:
                    continue
                if not item.is_dir():
                    continue
                try:
                    if not any(item.iterdir()):
                        yield item
                except PermissionError:
                    continue

        print("\n Searching for empty folders (including nested ones)...")
        candidates = list(_empty_dirs())

        if not candidates:
            print(" No empty folders found.")
            return

        for c in candidates:
            tag = " [preview]" if self.dry_run else ""
            print(f"{tag} {self._rel(c)}")
        print(f" Total empty folders: {len(candidates)}")

        if self.dry_run:
            print(" (Preview mode is on. Additional empty folders may appear later if they")
            print("  only become empty after their subfolders are removed - rerun this")
            print("  command after applying real changes.)")
            return

        if not self._confirm(" Move these folders to the trash bin?"):
            print(" Operation cancelled.")
            return

        # Re-walk live so a parent that becomes empty after its child is
        # trashed gets caught in this same run (cascading collapse).
        self._begin_batch()
        moved = 0
        for item in _empty_dirs():
            if item.exists() and self._stage_item(item):
                moved += 1
        self._end_batch()
        print(f" Moved {moved} folder(s) to the trash bin ({TRASH_DIRNAME}).")

    def delete_batch(self, file_list: list[str]):
        print(f"\n Processing the specified batch of files ({len(file_list)} item(s))...")
        matches = []
        for name in file_list:
            p = self.target_dir / name
            if p.exists():
                matches.append(p)
            else:
                print(f" ⚠️ [not found] {name}")
        self._process_matches(matches)

    # ------------------------------------------------------------------ #
    # Trash bin management
    # ------------------------------------------------------------------ #

    def show_trash(self):
        trash_root = self._trash_root()
        if not trash_root.exists() or not any(trash_root.iterdir()):
            print(" The trash bin is empty.")
            return

        batches = sorted((b for b in trash_root.iterdir() if b.is_dir()), reverse=True)
        print(f"\n Trash bin ({len(batches)} batch(es)):")
        for b in batches:
            manifest = b / MANIFEST_FILENAME
            count = 0
            if manifest.exists():
                with open(manifest, "r", encoding="utf-8") as mf:
                    count = sum(1 for line in mf if line.strip())
            marker = "  <-- restorable with 'restore'" if b == self._last_batch_for_restore else ""
            print(f"  - {b.name}  ({count} item(s)){marker}")
        print(" Type 'restore' to bring back the most recent batch, or 'purge' to permanently empty the bin.")

    def restore_last_batch(self):
        if self._last_batch_for_restore is None or not self._last_batch_for_restore.exists():
            print(" There is no recent batch to restore in this session.")
            print(f" You can browse the trash bin manually here: {self._trash_root()}")
            return

        batch = self._last_batch_for_restore
        manifest_path = batch / MANIFEST_FILENAME
        if not manifest_path.exists():
            print(" Could not find this batch's manifest - automatic restore isn't possible.")
            return

        with open(manifest_path, "r", encoding="utf-8") as mf:
            lines = [line.rstrip("\n") for line in mf if line.strip()]

        restored, failed = 0, 0
        remaining_lines = []
        for line in lines:
            if "\t" not in line:
                continue
            safe_name, original_path = line.split("\t", 1)
            src = batch / safe_name
            dest = Path(original_path)
            if not src.exists():
                continue
            if dest.exists():
                print(f" ⚠️ Skipping {dest.name}: another item already exists at its original location.")
                failed += 1
                remaining_lines.append(line)
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                restored += 1
            except Exception as e:
                print(f" [error] could not restore {dest.name}: {e}")
                failed += 1
                remaining_lines.append(line)

        self._log("RESTORE", batch.name, f"restored={restored} failed={failed}")

        if failed == 0:
            # Everything came back safely - the batch folder is now empty
            # and can be removed along with its manifest.
            manifest_path.unlink(missing_ok=True)
            shutil.rmtree(batch, ignore_errors=True)
            self._last_batch_for_restore = None
            print(f" Restored {restored} item(s).")
        else:
            # Do NOT delete the batch folder - items that failed to restore
            # (e.g. name collision) must stay safely in the trash. Rewrite
            # the manifest to only the still-pending items so a later
            # 'restore' retry (after resolving the collision) picks up
            # where this one left off.
            with open(manifest_path, "w", encoding="utf-8") as mf:
                mf.write("\n".join(remaining_lines) + ("\n" if remaining_lines else ""))
            print(f" Restored {restored} item(s). {failed} item(s) remain in the trash bin")
            print(f" ({TRASH_DIRNAME}/{batch.name}) due to a name conflict - rename or move the")
            print(" conflicting file, then type 'restore' again to retry.")

    def empty_trash(self):
        trash_root = self._trash_root()
        if not trash_root.exists() or not any(trash_root.iterdir()):
            print(" The trash bin is already empty.")
            return

        print(" ⚠️  This will permanently delete everything in the trash bin. This cannot be undone.")
        try:
            answer = input(" Type PURGE (uppercase) to confirm > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[cancelled] Operation cancelled.")
            return

        if answer != "PURGE":
            print(" Cancelled.")
            return

        shutil.rmtree(trash_root)
        self._last_batch_for_restore = None
        self._log("PURGE", TRASH_DIRNAME, "Permanently deleted all trash bin contents")
        print(" The trash bin has been permanently emptied.")

    # ------------------------------------------------------------------ #
    # REPL
    # ------------------------------------------------------------------ #

    def start(self):
        print(BANNER)
        print(f" Current directory: {self.target_dir}")
        print(" Type 'help' to see the list of available commands.\n")

        while True:
            mode_str = "preview only - safe" if self.dry_run else "real mode - moves to trash"
            try:
                user_input = input(f"PyClean [{mode_str}] > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break

            if not user_input:
                continue

            try:
                parts = shlex.split(user_input)
            except ValueError as e:
                print(f" Error parsing command (check your quotes are closed): {e}")
                continue

            if not parts:
                continue

            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ["exit", "quit"]:
                print("Closing PyClean.")
                break

            elif cmd == "help":
                self.print_help()

            elif cmd == "dryrun":
                self.dry_run = not self.dry_run
                status = "enabled (safe)" if self.dry_run else "disabled (items will actually be moved to the trash bin)"
                print(f" Preview mode is now: {status}")

            elif cmd == "dir":
                if args:
                    new_path = Path(args[0]).expanduser().resolve()
                    if new_path.exists() and new_path.is_dir():
                        self.target_dir = new_path
                        print(f" Changed directory to: {self.target_dir}")
                    else:
                        print(" That directory does not exist.")
                else:
                    print(f"Current directory: {self.target_dir}")

            elif cmd == "prefix":
                clean_args, recursive = self._extract_recursive_flag(args)
                if clean_args:
                    self.delete_by_prefix(clean_args[0], recursive=recursive)
                else:
                    print(" Error: please specify the text to match (example: prefix temp_ [-r])")

            elif cmd == "suffix":
                clean_args, recursive = self._extract_recursive_flag(args)
                if clean_args:
                    self.delete_by_suffix(clean_args[0], recursive=recursive)
                else:
                    print(" Error: please specify the text to match (example: suffix _old [-r])")

            elif cmd == "ext":
                clean_args, recursive = self._extract_recursive_flag(args)
                if clean_args:
                    self.delete_by_extensions(clean_args, recursive=recursive)
                else:
                    print(" Error: please specify at least one extension (example: ext jpg mp4 [-r])")

            elif cmd == "empty":
                self.delete_empty_folders()

            elif cmd == "batch":
                if args:
                    clean_files = [a.rstrip(",").strip() for a in args if a.rstrip(",").strip()]
                    self.delete_batch(clean_files)
                else:
                    print(" Error: please provide file names (example: batch file1.jpg file2.mp4)")

            elif cmd == "trash":
                self.show_trash()

            elif cmd == "restore":
                self.restore_last_batch()

            elif cmd == "purge":
                self.empty_trash()

            else:
                print(f" Unknown command '{cmd}'. Type 'help' to see the command list.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PyClean - interactive tool for safe file and folder cleanup, By M-Bouri"
    )
    parser.add_argument("-p", "--path", default=".", help="Initial working directory")
    args = parser.parse_args()

    cleaner = PyCleaner(args.path)
    cleaner.start()
