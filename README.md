[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "jukto"
version = "0.1.0"
description = "A unified Python SDK for Bangladesh's third-party APIs (SMS, Logistics, Payment)."
readme = "README.md"
requires-python = ">=3.9"
license = "MIT"
authors = [
  { name = "Mehedi Hasan Faysal", email = "mahdibuilds.hq@gmail.com" },
]
classifiers = [
  "Programming Language :: Python :: 3",
  "License :: OSI Approved :: MIT License",
  "Operating System :: OS Independent",
]
dependencies = [
  "httpx",
]

[project.urls]
"Homepage" = "https://github.com/jukto-sdk/jukto-python"
"Bug Tracker" = "https://github.com/jukto-sdk/jukto-python/issues"
