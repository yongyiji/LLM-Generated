#!/usr/bin/env python3

from pathlib import Path
import json
import re
import ast
import os
import argparse

DEFAULT_TEXT_EXTS = {".md"}
DEFAULT_CODE_EXTS = {".go", ".java", ".js", ".ts", ".php", ".py", ".rb"}

# ---------------- Argument Parsing ----------------
def parse_args():
    parser = argparse.ArgumentParser(description="Classify repo files and extract content.")
    parser.add_argument("--repo_path", required=True, help="Path to the repository to scan")
    parser.add_argument("--output_dir", required=True, help="Output directory path")
    parser.add_argument("--code-ext", default=None, help="Custom code extensions (comma-separated)")
    parser.add_argument("--text-ext", default=None, help="Custom text extensions (comma-separated)")
    parser.add_argument("--max_words", type=int, default=512, help="Maximum words per chunk (default 512)")
    return parser.parse_args()

def normalize_ext_list(ext_str):
    if not ext_str:
        return None
    exts = set()
    for p in ext_str.split(","):
        p = p.strip()
        if p and not p.startswith("."):
            p = "." + p
        if p:
            exts.add(p.lower())
    return exts

# ---------------- File Classification ----------------
def classify_files(repo_path: Path, text_exts, code_exts):
    text_files, code_files, other_files = [], [], []
    for p in repo_path.rglob("*"):
        if p.is_file():
            ext = p.suffix.lower()
            if ext in text_exts:
                text_files.append(str(p))
            elif ext in code_exts:
                code_files.append(str(p))
            else:
                other_files.append(str(p))
    return text_files, code_files, other_files

def save_as_jsonl(file_list, output_path, ftype):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for file in file_list:
            f.write(json.dumps({"type": ftype, "path": file}, ensure_ascii=False) + "\n")
    print(f"Saved {len(file_list)} {ftype} files -> {output_path}")
    return output_path

def load_file_list(jsonl_path):
    paths = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            paths.append(data["path"])
    return paths

# ---------------- Save Text/Other Content ----------------
def save_text_content(file_paths, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f_out:
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                f_out.write(json.dumps({"path": path, "content": content}, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"Cannot read {path}: {e}")
    print(f"Saved text contents -> {output_path}")

def save_other_content(file_paths, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f_out:
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                f_out.write(json.dumps({"path": path, "content": content}, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"Skipped {path}: {e}")
    print(f"Saved other files -> {output_path}")

# ---------------- Split Code and Comments ----------------
def split_code_and_comments(content):
    code_lines, comment_lines = [], []
    # Remove block comments /* ... */
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            comment_lines.append(line)
        else:
            code_lines.append(line)
    return "\n".join(code_lines).strip(), "\n".join(comment_lines).strip()

def save_code_comment_split(code_paths, code_output, comment_output):
    with open(code_output, "w", encoding="utf-8") as code_f, open(comment_output, "w", encoding="utf-8") as com_f:
        for path in code_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                code, comments = split_code_and_comments(content)
                if code:
                    code_f.write(json.dumps({"path": path, "code": code}, ensure_ascii=False) + "\n")
                if comments:
                    com_f.write(json.dumps({"path": path, "comments": comments}, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"Failed {path}: {e}")
    print(f"Saved code/comment splits")

# ---------------- Code Block Splitting ----------------
def detect_lang(path):
    ext = Path(path).suffix.lower()
    return {
        ".py": "python", ".java": "java", ".js": "js",
        ".ts": "ts", ".go": "go", ".php": "php", ".rb": "ruby"
    }.get(ext, "unknown")

def split_python_code(code):
    try:
        tree = ast.parse(code)
        lines = code.splitlines()
        blocks = []
        for node in tree.body:
            s, e = getattr(node, "lineno", None), getattr(node, "end_lineno", None)
            if s and e:
                blocks.append("\n".join(lines[s - 1:e]))
        return blocks or [code]
    except Exception:
        return [code]

def split_java_code(code):
    lines = code.splitlines()
    blocks, stack, start = [], [], 0
    for i, line in enumerate(lines):
        if "{" in line:
            stack.append("{")
        if "}" in line and stack:
            stack.pop()
        if not stack and "{" in line:
            blocks.append("\n".join(lines[start:i + 1]).strip())
            start = i + 1
    if start < len(lines):
        rest = "\n".join(lines[start:]).strip()
        if rest:
            blocks.append(rest)
    return blocks or [code]

def split_js_code(code):
    """Split JS/TS by function/class blocks"""
    lines = code.splitlines()
    blocks, buffer, brace_depth = [], [], 0
    for line in lines:
        buffer.append(line)
        if re.match(r'^\s*//', line):
            continue
        brace_depth += line.count("{")
        brace_depth -= line.count("}")
        if brace_depth == 0 and buffer and "{" in line:
            block = "\n".join(buffer).strip()
            if block:
                blocks.append(block)
            buffer = []
    if buffer:
        block = "\n".join(buffer).strip()
        if block:
            blocks.append(block)
    return blocks or [code]

def split_go_code(code):
    """Split Go by func/type blocks"""
    lines = code.splitlines()
    blocks, buffer, brace_depth = [], [], 0
    for line in lines:
        buffer.append(line)
        if re.match(r'^\s*(func|type|var|const)\b', line):
            brace_depth = 0
        brace_depth += line.count("{")
        brace_depth -= line.count("}")
        if brace_depth == 0 and "{" in line:
            block = "\n".join(buffer).strip()
            if block:
                blocks.append(block)
            buffer = []
    if buffer:
        rest = "\n".join(buffer).strip()
        if rest:
            blocks.append(rest)
    return blocks or [code]

def split_ruby_code(code):
    """Split Ruby by def...end or class...end"""
    lines = code.splitlines()
    blocks, buffer = [], []
    depth = 0
    for line in lines:
        stripped = line.strip()
        buffer.append(line)
        if re.match(r'^(class|module|def)\b', stripped):
            depth += 1
        elif stripped == "end" and depth > 0:
            depth -= 1
            if depth == 0:
                block = "\n".join(buffer).strip()
                if block:
                    blocks.append(block)
                buffer = []
    if buffer:
        rest = "\n".join(buffer).strip()
        if rest:
            blocks.append(rest)
    return blocks or [code]

def split_code_blocks(input_jsonl, output_jsonl, max_words=512):
    """
    Improved version:
    - If total words <= max_words: save as idx.1
    - If exceeds max_words: split by language structure (functions, classes, etc.)
    - No longer splits by lines; preserves function integrity
    """
    def count_words(s):
        return len(re.findall(r"\w+", s))

    with open(input_jsonl, "r", encoding="utf-8") as f_in, open(output_jsonl, "w", encoding="utf-8") as f_out:
        for idx, line in enumerate(f_in, start=1):
            data = json.loads(line)
            path, code = data["path"], data["code"]
            lang = detect_lang(path)
            total_words = count_words(code)

            # Step 1: Short files not split
            if total_words <= max_words:
                f_out.write(json.dumps({
                    "global_id": f"{idx}.1",
                    "path": path,
                    "lang": lang,
                    "code": code
                }, ensure_ascii=False) + "\n")
                continue

            # Step 2: Long files split by language structure
            if lang == "python":
                blocks = split_python_code(code)
            elif lang == "java":
                blocks = split_java_code(code)
            elif lang in {"js", "ts"}:
                blocks = split_js_code(code)
            elif lang == "go":
                blocks = split_go_code(code)
            elif lang == "ruby":
                blocks = split_ruby_code(code)
            else:
                blocks = [code]

            # Step 3: Output language-level blocks
            for j, block in enumerate(blocks, start=1):
                f_out.write(json.dumps({
                    "global_id": f"{idx}.{j}",
                    "path": path,
                    "lang": lang,
                    "code": block
                }, ensure_ascii=False) + "\n")
    print(f"Saved code_content_small_trunk.jsonl (split by structure only if > {max_words} words)")

def split_comment_blocks(input_jsonl, output_jsonl):
    with open(input_jsonl, "r", encoding="utf-8") as f_in, open(output_jsonl, "w", encoding="utf-8") as f_out:
        for idx, line in enumerate(f_in, start=1):
            data = json.loads(line)
            path, comments = data.get("path"), data.get("comments", "")
            if not comments:
                continue
            lines = [l for l in comments.splitlines() if l.strip()]
            for j, block in enumerate(lines, start=1):
                f_out.write(json.dumps({
                    "global_id": f"{idx}.{j}",
                    "path": path,
                    "comments": block
                }, ensure_ascii=False) + "\n")
    print(f"Saved comments_content_small_trunk.jsonl")

# ---------------- Sentence Chunking (Markdown / Comments) ----------------
def split_text_into_sentences(text):
    sents = re.split(r'([。！？!?\.])', text)
    if not sents:
        return []
    paired = ["".join(x) for x in zip(sents[0::2], sents[1::2])]
    if len(sents) % 2 != 0:
        paired.append(sents[-1])
    return [s.strip() for s in paired if s.strip()]

def chunk_by_sentences(text, max_words=512):
    sents = split_text_into_sentences(text)
    chunks, cur, count = [], [], 0
    for s in sents:
        words = s.split()
        if count + len(words) > max_words and cur:
            chunks.append(" ".join(cur))
            cur, count = [], 0
        cur.append(s)
        count += len(words)
    if cur:
        chunks.append(" ".join(cur))
    return chunks

def save_markdown_chunks_as_json(input_jsonl, output_json, max_words=512):
    data_list = []
    with open(input_jsonl, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            d = json.loads(line)
            path, content = d["path"], d["content"]
            if not path.lower().endswith(".md"):
                continue
            chunks = chunk_by_sentences(content, max_words)
            for j, chunk in enumerate(chunks, start=1):
                data_list.append({
                    "global_id": f"{i}.{j}",
                    "path": path,
                    "text": chunk
                })
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
    print(f"Saved text_content_small_size.json (JSON array)")

def save_comment_chunks_as_json(input_jsonl, output_json, max_words=512):
    data_list = []
    with open(input_jsonl, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            d = json.loads(line)
            path, comments = d["path"], d.get("comments", "")
            if not comments:
                continue
            chunks = chunk_by_sentences(comments, max_words)
            for j, chunk in enumerate(chunks, start=1):
                data_list.append({
                    "global_id": f"{i}.{j}",
                    "path": path,
                    "comments": chunk
                })
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
    print(f"Saved comments_content_small_size.json (JSON array)")

# ---------------- Main Workflow ----------------
def main():
    args = parse_args()
    repo = Path(args.repo_path).resolve()
    out = Path(args.output_dir).resolve()
    text_ext = normalize_ext_list(args.text_ext) or DEFAULT_TEXT_EXTS
    code_ext = normalize_ext_list(args.code_ext) or DEFAULT_CODE_EXTS
    print(f"Repo: {repo}")
    print(f"Output: {out}")

    # Classification
    text_files, code_files, other_files = classify_files(repo, text_ext, code_ext)
    text_jsonl = save_as_jsonl(text_files, out / "text_files.jsonl", "text")
    code_jsonl = save_as_jsonl(code_files, out / "code_files.jsonl", "code")
    other_jsonl = save_as_jsonl(other_files, out / "other_files.jsonl", "other")

    # Content extraction
    save_text_content(load_file_list(text_jsonl), out / "text_content_files.jsonl")
    save_code_comment_split(load_file_list(code_jsonl), out / "code_content_only.jsonl", out / "comments_content_only.jsonl")
    save_other_content(load_file_list(other_jsonl), out / "other_content_files.jsonl")

    # Block splitting
    split_code_blocks(out / "code_content_only.jsonl", out / "code_content_small_trunk.jsonl")
    split_comment_blocks(out / "comments_content_only.jsonl", out / "comments_content_small_trunk.jsonl")

    # Markdown and Comment JSON arrays
    save_markdown_chunks_as_json(out / "text_content_files.jsonl", out / "text_content_small_size.json", args.max_words)
    save_comment_chunks_as_json(out / "comments_content_only.jsonl", out / "comments_content_small_size.json", args.max_words)

    print("\nAll 11 files generated successfully!")

if __name__ == "__main__":
    main()