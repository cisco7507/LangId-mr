# Open-source components and license summary

Generated: 2025-11-17

This document lists the main open-source packages used by this project, the license identified from the package/project pages, whether commercial use is allowed under that license, and short notes about conditions and caveats. This is an informational summary, not legal advice — verify license text and consult legal counsel for redistribution/redistribution-with-binaries or policy-critical use.

| Dependency | Ecosystem | License (as found) | Commercial use allowed? | Conditions / Notes | Reference |
|---|---:|---|:---:|---|---|
| fastapi | Python | MIT | Yes | Include copyright & license notices when distributing. | https://pypi.org/project/fastapi/ |
| uvicorn | Python | BSD (2/3) | Yes | Include copyright & license notices. | https://pypi.org/project/uvicorn/ |
| loguru | Python | MIT | Yes | Include copyright & license notices. | https://pypi.org/project/loguru/ |
| python-multipart | Python | Apache-2.0 | Yes | Preserve NOTICE/attribution; patent grant/termination terms apply. | https://pypi.org/project/python-multipart/ |
| SQLAlchemy | Python | MIT | Yes | Include copyright & license notices. | https://pypi.org/project/SQLAlchemy/ |
| prometheus-client | Python | (see project) — typically permissive (Apache-2.0) | Yes (verify) | Verify exact license for the specific version used. | https://pypi.org/project/prometheus-client/ |
| faster-whisper | Python | (verify on project repo) | Likely yes (verify) | Please confirm license on the upstream repo before redistribution. | https://pypi.org/project/faster-whisper/ |
| torch (PyTorch) | Python | BSD-style | Yes | PyTorch distributed under BSD-style; pre-trained models and datasets may carry separate licenses — verify model/dataset licenses. | https://pypi.org/project/torch/ |
| torchaudio | Python | BSD-style (verify) | Yes | Models/datasets may have separate licenses; confirm if using pretrained models. | https://pypi.org/project/torchaudio/ |
| transformers | Python | Apache-2.0 | Yes | Apache requires NOTICE and includes a patent clause; pretrained model weights/datasets may have separate licenses. | https://pypi.org/project/transformers/ |
| sentencepiece | Python | Apache-2.0 | Yes | Preserve NOTICE; verify if bundling any external models. | https://pypi.org/project/sentencepiece/ |
| pytest | Python (dev) | MIT | Yes | Test frameworks: include license when distributing. No runtime distribution required. | https://pypi.org/project/pytest/ |
| pytest-cov | Python (dev) | MIT | Yes | Dev/test-only dependency. | https://pypi.org/project/pytest-cov/ |
| httpx | Python | BSD | Yes | Include copyright & license notices. | https://pypi.org/project/httpx/ |
| av (PyAV) | Python | BSD-permissive (PyAV) — note: FFmpeg codecs may be LGPL/GPL | Conditional | PyAV itself is permissive, but linking or redistributing FFmpeg binaries/codecs may trigger LGPL/GPL obligations — verify distro scenario. | https://pypi.org/project/av/ |
| soundfile | Python | BSD 3-Clause | Yes | Include copyright & license notices. | https://pypi.org/project/soundfile/ |
| numpy | Python | BSD | Yes | Include copyright & license notices. | https://pypi.org/project/numpy/ |
| python-dotenv | Python | BSD-style | Yes | Include copyright & license notices. | https://pypi.org/project/python-dotenv/ |

| react | JavaScript | MIT | Yes | Include license/copyright notices when distributing. | https://www.npmjs.com/package/react |
| react-dom | JavaScript | MIT | Yes | Same as `react`. | https://www.npmjs.com/package/react-dom |
| tailwindcss | JavaScript | MIT | Yes | Include license notice. | https://www.npmjs.com/package/tailwindcss |
| web-vitals | JavaScript | Apache-2.0 | Yes | Preserve NOTICE (if applicable). | https://www.npmjs.com/package/web-vitals |
| react-scripts | JavaScript (dev) | MIT | Yes | Dev tooling; include license in any redistributed build artifacts as required. | https://www.npmjs.com/package/react-scripts |
| postcss | JavaScript | MIT | Yes | Include license notice. | https://www.npmjs.com/package/postcss |
| autoprefixer | JavaScript | MIT | Yes | Include license notice. | https://www.npmjs.com/package/autoprefixer |
| cross-env | JavaScript (dev) | MIT | Yes | Include license notice. | https://www.npmjs.com/package/cross-env |
| @testing-library/* | JavaScript (dev) | MIT | Yes | Test utilities — dev-only. | https://www.npmjs.com/ |

## Summary & Important Caveats

- "Commercial use allowed?" is answered according to the package license (MIT, BSD, Apache-2.0 permit commercial use). MIT and BSD require preserving copyright and license notices; Apache-2.0 requires preservation of NOTICE and includes a patent grant with termination clauses — read the license text.

- Some project components reference or use pretrained models, checkpoints or datasets (for example: `transformers`, `torch`, `torchaudio`). Those models/datasets can have separate licenses and usage restrictions (e.g., non-commercial, research-only, or additional attribution). If you ship or rely on external pretrained artifacts, verify their licenses separately.

- Native libraries and codec toolchains: `av` (PyAV) wraps FFmpeg; FFmpeg builds and some codecs may be licensed under LGPL or GPL which can affect redistribution. If you redistribute binaries that include FFmpeg or link GPL parts, consult legal counsel.

- `faster-whisper`: the package metadata on PyPI may not include an explicit license string for some versions; verify the project's GitHub repo/license file before redistributing or bundling.

- This document is informational only and does not replace legal review. For any product redistribution, redistribution with proprietary binaries, or where license compliance is material to the business, consult your legal team and inspect the exact license text of each dependency and any associated data/model files.

---

If you want, I can:
- expand this table with exact version numbers currently installed (from `pip freeze` / `package-lock.json`),
- add direct license file excerpts for each package and include them inline or in a `licenses/` folder,
- or produce a machine-readable SPDX summary file.

Which of those would you like next?