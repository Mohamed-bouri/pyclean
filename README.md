# PyClean

```text
 ___           ___    _                        
(  _`\        (  _`\ (_ )                      
| |_) ) _   _ | ( (_) | |    __     _ _   ___  
| ,__/'( ) ( )| |  _  | |  /'__`\ /'_` )/' _ `\
| |    | (_) || (_( ) | | (  ___/( (_| || ( ) |
(_)    `\__, |(____/'(___)`\____)`\__,_)(_) (_)
       ( )_| |                                 
       `\___/'                      By M-Bouri            
                                         
                                         
```

> An interactive command-line file cleaner with an Arabic-language interface, a bit-safe trash bin instead of permanent deletion, and dry-run preview by default.

**Author:** M-Bouri

---

## Requirements

Python 3.7+. Zero external dependencies — built entirely with the standard library (`pathlib`, `shutil`, `shlex`, `argparse`, `uuid`, `datetime`).

---

## Features

* **Dry-run by default** — nothing is touched until you explicitly switch out of preview mode with `dryrun`.
* **Trash bin, not permanent deletion** — "real" mode moves matched items into a local `.pyclean_trash/` folder instead of deleting them outright. Nothing is unrecoverable until you explicitly `purge`.
* **Restore** — bring back the most recent trash batch with one command.
* **Confirmation before every real action** — every command that would move files shows you the full match list first and asks for explicit `yes`/`no` confirmation.
* **Recursive search** — `prefix`, `suffix`, and `ext` all support an optional `-r` flag to search subdirectories too.
* **Cascading empty-folder cleanup** — the `empty` command correctly collapses nested empty folders (a folder that only becomes empty after its child is removed still gets caught in the same run).
* **Audit log** — every action is timestamped and recorded to `pyclean_log.txt` in the working directory.
* **Collision-safe restore** — if restoring would overwrite a file that already exists at the original location, that one item is safely left in the trash bin (not lost) and reported, instead of silently overwriting.

---

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mohamed-bouri/pyclean.git
   cd pyclean
   ```

2. **Run it, optionally pointing at a starting directory:**
   ```bash
   python3 pyclean.py -p ./some_folder
   ```
   Without `-p`, it starts in the current directory.

3. **You land in an interactive prompt, in preview (dry-run) mode by default:**
   ```
   PyClean [preview only - safe] >
   ```
   Type `help` to see all commands.

---

## How the Safety Model Works

Most one-line "delete files matching X" scripts have exactly one bad moment: a wrong flag or an unintended match, in real mode, and it's gone. PyClean is built around never letting that be a single, unconfirmed, irreversible step.

**Two independent safety layers, on by default:**

1. **Dry-run mode** (`dry_run = True` at startup) — commands only *preview* what would happen. Toggle with `dryrun`.
2. **Trash bin, not `unlink()`** — once you switch dry-run off, matched items aren't deleted; they're moved into `.pyclean_trash/<timestamp>/` in the working directory, and every command still shows you the full match list and asks `(yes/no)` before touching anything.

Nothing is truly gone until you run `purge`, which requires typing the literal word `PURGE` (not just "yes") to confirm — separate friction for the one truly irreversible action in the tool.

```
PyClean [real mode - moves to trash] > ext tmp log
 Searching for files with extension(s): {'tmp', 'log'} (current directory only)...
 build.tmp
 debug.log
 Total matching items: 2
 Move these 2 item(s) to the trash bin? (yes/no) > yes
 [moved to trash] build.tmp
 [moved to trash] debug.log
 Moved 2/2 item(s) to the trash bin (.pyclean_trash).
```

---

## Command Reference

| Command | Description |
| --- | --- |
| `help` | Show the full command list. |
| `prefix <text> [-r]` | Match files starting with `<text>`. `-r` also searches subdirectories. |
| `suffix <text> [-r]` | Match files ending with `<text>` (before the extension). |
| `ext <ext1> <ext2>.. [-r]` | Match files by one or more extensions, e.g. `ext jpg mp4 -r`. |
| `empty` | Find and clear empty folders, including nested ones that only become empty once their contents are removed. |
| `batch <file1> <file2>..` | Target a specific, explicit list of file/folder names. Supports quoted names with spaces. |
| `trash` | List what's currently sitting in the trash bin, grouped by batch. |
| `restore` | Restore the most recent trash batch back to its original location. |
| `purge` | **Permanently** empty the trash bin. Requires typing `PURGE` to confirm. |
| `dryrun` | Toggle between preview mode and real (trash-moving) mode. |
| `dir <path>` | Change the current working directory. |
| `exit` / `quit` | Leave the tool. |

---

## Example Session

```
$ python3 pyclean.py -p ./downloads
 ___           ___    _                        
(  _`\        (  _`\ (_ )                      
| |_) ) _   _ | ( (_) | |    __     _ _   ___  
| ,__/'( ) ( )| |  _  | |  /'__`\ /'_` )/' _ `\
| |    | (_) || (_( ) | | (  ___/( (_| || ( ) |
(_)    `\__, |(____/'(___)`\____)`\__,_)(_) (_)
       ( )_| |                                 
       `\___/'                      By M-Bouri            
                                                 
                                         
 Current directory: /home/user/downloads
 Type 'help' to see the list of available commands.

PyClean [preview only - safe] > prefix temp_
 Searching for files starting with 'temp_' (current directory only)...
 [preview] temp_file1.txt
 [preview] temp_file2.log
 Total matching items: 2
 (Preview mode is on - nothing was moved. Type 'dryrun' to switch to real mode)

PyClean [preview only - safe] > dryrun
 Preview mode is now: disabled (items will actually be moved to the trash bin)

PyClean [real mode - moves to trash] > prefix temp_
 Searching for files starting with 'temp_' (current directory only)...
 temp_file1.txt
 temp_file2.log
 Total matching items: 2
 Move these 2 item(s) to the trash bin? (yes/no) > yes
 [moved to trash] temp_file1.txt
 [moved to trash] temp_file2.log
 Moved 2/2 item(s) to the trash bin (.pyclean_trash).

PyClean [real mode - moves to trash] > restore
 Restored 2 item(s).
```

---

## Restore Scope

`restore` brings back the most recently created batch **from the current running session**. If you close PyClean and reopen it, that in-memory pointer resets — but nothing is lost, since every past batch is still sitting on disk under `.pyclean_trash/<timestamp>/`, each with its own manifest mapping trashed names back to original paths. You can always inspect that folder directly, or check `trash` at the start of a new session to see what's there.

## Limitations

* `prefix`, `suffix`, and `ext` only scan the top-level directory unless you pass `-r`.
* Trash batches, and the audit log, live inside the directory you're cleaning (`.pyclean_trash/`, `pyclean_log.txt`). If you delete that directory itself from outside PyClean, the trash goes with it.
* `restore` skips (rather than overwrites) any item whose original location now has something else in it; resolve the conflict and run `restore` again to pick up the rest.

---

## License

Distributed under the **MIT License**. See `LICENSE` for details.
