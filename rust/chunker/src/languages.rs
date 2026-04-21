use regex::Regex;
use std::sync::OnceLock;

/// Language-aware separator registry.
/// Each language defines regex separators ordered from high-level (class/function
/// boundaries) down to low-level (blank lines, single newlines).
pub struct LanguageSeparators {
    pub name: &'static str,
    pub aliases: &'static [&'static str],
    pub extensions: &'static [&'static str],
    pub separators: Vec<Regex>,
}

/// Compile a list of pattern strings into a `Vec<Regex>`.
/// Patterns starting with `^` automatically get the `(?m)` multiline flag.
fn compile(patterns: &[&str]) -> Vec<Regex> {
    patterns
        .iter()
        .map(|p| {
            let pat = if p.starts_with('^') {
                format!("(?m){}", p)
            } else {
                (*p).to_string()
            };
            Regex::new(&pat).unwrap_or_else(|e| panic!("bad regex '{}': {}", p, e))
        })
        .collect()
}

fn build_registry() -> Vec<LanguageSeparators> {
    vec![
        // 1. Python
        LanguageSeparators {
            name: "python",
            aliases: &["py", "python3"],
            extensions: &["py"],
            separators: compile(&[
                r"^class ",
                r"^def ",
                r"^async def ",
                r"^\s+def ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 2. JavaScript
        LanguageSeparators {
            name: "javascript",
            aliases: &["js", "ecmascript"],
            extensions: &["js"],
            separators: compile(&[
                r"^function ",
                r"^const .* = ",
                r"^class ",
                r"^export ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 3. TypeScript
        LanguageSeparators {
            name: "typescript",
            aliases: &["ts"],
            extensions: &["ts"],
            separators: compile(&[
                r"^function ",
                r"^const .* = ",
                r"^class ",
                r"^export ",
                r"^interface ",
                r"^type ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 4. TSX
        LanguageSeparators {
            name: "tsx",
            aliases: &[],
            extensions: &["tsx"],
            separators: compile(&[
                r"^function ",
                r"^const .* = ",
                r"^class ",
                r"^export ",
                r"^interface ",
                r"^type ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 5. Rust
        LanguageSeparators {
            name: "rust",
            aliases: &["rs"],
            extensions: &["rs"],
            separators: compile(&[
                r"^fn ",
                r"^pub fn ",
                r"^impl ",
                r"^struct ",
                r"^enum ",
                r"^mod ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 6. Go
        LanguageSeparators {
            name: "go",
            aliases: &["golang"],
            extensions: &["go"],
            separators: compile(&[
                r"^func ",
                r"^type ",
                r"^package ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 7. Java
        LanguageSeparators {
            name: "java",
            aliases: &[],
            extensions: &["java"],
            separators: compile(&[
                r"^public ",
                r"^private ",
                r"^protected ",
                r"^class ",
                r"^interface ",
                r"@",
                r"\n\n",
                r"\n",
            ]),
        },
        // 8. C
        LanguageSeparators {
            name: "c",
            aliases: &[],
            extensions: &["c"],
            separators: compile(&[
                r"^#",
                r"^\w+.*\{",
                r"\n\n",
                r"\n",
            ]),
        },
        // 9. C++
        LanguageSeparators {
            name: "cpp",
            aliases: &["c++", "cxx", "cc"],
            extensions: &["cpp", "cc", "cxx", "h", "hpp"],
            separators: compile(&[
                r"^#",
                r"^\w+.*\{",
                r"^class ",
                r"^template",
                r"^namespace ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 10. C#
        LanguageSeparators {
            name: "csharp",
            aliases: &["cs", "c#"],
            extensions: &["cs"],
            separators: compile(&[
                r"^public ",
                r"^private ",
                r"^class ",
                r"^namespace ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 11. Ruby
        LanguageSeparators {
            name: "ruby",
            aliases: &["rb"],
            extensions: &["rb"],
            separators: compile(&[
                r"^class ",
                r"^module ",
                r"^def ",
                r"^end",
                r"\n\n",
                r"\n",
            ]),
        },
        // 12. PHP
        LanguageSeparators {
            name: "php",
            aliases: &[],
            extensions: &["php"],
            separators: compile(&[
                r"^function ",
                r"^class ",
                r"^namespace ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 13. Swift
        LanguageSeparators {
            name: "swift",
            aliases: &[],
            extensions: &["swift"],
            separators: compile(&[
                r"^func ",
                r"^class ",
                r"^struct ",
                r"^protocol ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 14. Kotlin
        LanguageSeparators {
            name: "kotlin",
            aliases: &["kt"],
            extensions: &["kt", "kts"],
            separators: compile(&[
                r"^fun ",
                r"^class ",
                r"^object ",
                r"^interface ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 15. Scala
        LanguageSeparators {
            name: "scala",
            aliases: &[],
            extensions: &["scala"],
            separators: compile(&[
                r"^def ",
                r"^class ",
                r"^object ",
                r"^trait ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 16. Markdown
        LanguageSeparators {
            name: "markdown",
            aliases: &["md", "mdx"],
            extensions: &["md", "mdx"],
            separators: compile(&[
                r"^#{1,6} ",
                r"\n\n",
                r"\n",
                r"\. ",
            ]),
        },
        // 17. HTML
        LanguageSeparators {
            name: "html",
            aliases: &["htm"],
            extensions: &["html", "htm"],
            separators: compile(&[
                r"<h[1-6]",
                r"<div",
                r"<section",
                r"<p",
                r"\n\n",
                r"\n",
            ]),
        },
        // 18. CSS
        LanguageSeparators {
            name: "css",
            aliases: &["scss"],
            extensions: &["css", "scss"],
            separators: compile(&[
                r"^\}",
                r"^\.",
                r"^#",
                r"^@",
                r"\n\n",
                r"\n",
            ]),
        },
        // 19. JSON
        LanguageSeparators {
            name: "json",
            aliases: &[],
            extensions: &["json"],
            separators: compile(&[
                r#"^\s*"[^"]+"\s*:"#,
                r"\n",
            ]),
        },
        // 20. YAML
        LanguageSeparators {
            name: "yaml",
            aliases: &["yml"],
            extensions: &["yaml", "yml"],
            separators: compile(&[
                r"^[a-zA-Z_].*:",
                r"\n- ",
                r"\n",
            ]),
        },
        // 21. TOML
        LanguageSeparators {
            name: "toml",
            aliases: &[],
            extensions: &["toml"],
            separators: compile(&[
                r"^\[",
                r"\n\n",
                r"\n",
            ]),
        },
        // 22. XML
        LanguageSeparators {
            name: "xml",
            aliases: &[],
            extensions: &["xml"],
            separators: compile(&[
                r"<[a-zA-Z]",
                r"\n",
            ]),
        },
        // 23. SQL
        LanguageSeparators {
            name: "sql",
            aliases: &[],
            extensions: &["sql"],
            separators: compile(&[
                r"^SELECT ",
                r"^INSERT ",
                r"^UPDATE ",
                r"^DELETE ",
                r"^CREATE ",
                r"^ALTER ",
                r"^DROP ",
                r";",
                r"\n",
            ]),
        },
        // 24. R
        LanguageSeparators {
            name: "r",
            aliases: &[],
            extensions: &["r"],
            separators: compile(&[
                r"^\w+ <- function",
                r"\n\n",
                r"\n",
            ]),
        },
        // 25. Fortran
        LanguageSeparators {
            name: "fortran",
            aliases: &["f90", "f95", "f03"],
            extensions: &["f", "f90", "f95", "f03"],
            separators: compile(&[
                r"^subroutine ",
                r"^function ",
                r"^module ",
                r"^program ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 26. Pascal
        LanguageSeparators {
            name: "pascal",
            aliases: &["pas", "delphi", "dpr"],
            extensions: &["pas", "dpr"],
            separators: compile(&[
                r"^procedure ",
                r"^function ",
                r"^begin",
                r"^end",
                r"\n\n",
                r"\n",
            ]),
        },
        // 27. Solidity
        LanguageSeparators {
            name: "solidity",
            aliases: &["sol"],
            extensions: &["sol"],
            separators: compile(&[
                r"^contract ",
                r"^function ",
                r"^modifier ",
                r"^event ",
                r"\n\n",
                r"\n",
            ]),
        },
        // 28. DTD
        LanguageSeparators {
            name: "dtd",
            aliases: &[],
            extensions: &["dtd"],
            separators: compile(&[
                r"<!ELEMENT",
                r"<!ATTLIST",
                r"<!ENTITY",
                r"\n",
            ]),
        },
    ]
}

static REGISTRY: OnceLock<Vec<LanguageSeparators>> = OnceLock::new();

/// Return the full language registry (lazily initialised).
pub fn all_languages() -> &'static [LanguageSeparators] {
    REGISTRY.get_or_init(build_registry).as_slice()
}

/// Look up a language by name, alias, or file extension.
/// Extensions are matched with or without a leading dot.
pub fn lookup(name_or_ext: &str) -> Option<&'static LanguageSeparators> {
    let key = name_or_ext.to_ascii_lowercase();
    let langs = all_languages();

    // Exact name match
    if let Some(lang) = langs.iter().find(|l| l.name == key) {
        return Some(lang);
    }

    // Alias match
    if let Some(lang) = langs.iter().find(|l| l.aliases.contains(&key.as_str())) {
        return Some(lang);
    }

    // Extension match (strip optional leading dot)
    let ext = key.strip_prefix('.').unwrap_or(&key);
    langs.iter().find(|l| l.extensions.contains(&ext))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_languages_count() {
        assert_eq!(all_languages().len(), 28);
    }

    #[test]
    fn test_lookup_by_name() {
        assert!(lookup("python").is_some());
        assert!(lookup("rust").is_some());
        assert!(lookup("solidity").is_some());
    }

    #[test]
    fn test_lookup_by_alias() {
        assert_eq!(lookup("py").unwrap().name, "python");
        assert_eq!(lookup("js").unwrap().name, "javascript");
        assert_eq!(lookup("ts").unwrap().name, "typescript");
        assert_eq!(lookup("rs").unwrap().name, "rust");
        assert_eq!(lookup("golang").unwrap().name, "go");
    }

    #[test]
    fn test_lookup_by_extension() {
        assert_eq!(lookup(".py").unwrap().name, "python");
        assert_eq!(lookup("py").unwrap().name, "python");
        assert_eq!(lookup(".rs").unwrap().name, "rust");
        assert_eq!(lookup("hpp").unwrap().name, "cpp");
        assert_eq!(lookup(".kts").unwrap().name, "kotlin");
    }

    #[test]
    fn test_lookup_missing() {
        assert!(lookup("brainfuck").is_none());
    }

    #[test]
    fn test_each_language_has_separators() {
        for lang in all_languages() {
            assert!(
                !lang.separators.is_empty(),
                "language '{}' has no separators",
                lang.name
            );
        }
    }
}
