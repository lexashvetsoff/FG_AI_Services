import markdown


def md_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=[
            'tables',
            'fenced_code',
            'toc',
            'sane_lists'
        ]
    )
