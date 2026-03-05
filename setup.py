from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="alibabacloud-ack-mcp-server",
    version="1.0.1",
    author="AlibabaCloud",
    author_email="KeyOfSpectator@zju.edu.cn",
    description="AlibabaCloud Container Service MCP Server (ack-mcp-server)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aliyun/alibabacloud-ack-mcp-server",
    license="Apache-2.0",
    packages=find_packages(where="src", exclude=["tests", "tests.*"]),
    package_dir={"": "src"},
    # Include non-Python files specified in MANIFEST.in
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.12",
    install_requires=[
        "fastmcp>=2.12.2",
        "loguru>=0.7.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "alibabacloud-cs20151215>=4.9.0",
        "alibabacloud-credentials>=1.0.2",
        "alibabacloud-arms20190808>=10.0.1",
        "alibabacloud-sls20201230>=5.7.0",
        "alibabacloud-tea-util>=0.3.0",
        "alibabacloud-tea-openapi>=0.4.0",
        "kubernetes>=33.0.0",
        "httpx>=0.28.0",
        "requests>=2.32.0",
        "aiohttp>=3.12.0",
        "aiofiles>=24.0.0",
        "cachetools>=5.5.0",
        "pyyaml>=6.0.0",
    ],
    entry_points={
        "console_scripts": [
            "alibabacloud-ack-mcp-server = main_server:main",
        ],
    },
    keywords=["mcp", "kubernetes", "alibabacloud", "container-service"],
)
