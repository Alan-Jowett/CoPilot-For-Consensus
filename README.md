<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Copilot-for-Consensus
**An open-source AI assistant that ingests mailing list discussions, summarizes threads, and surfaces consensus for technical working groups.**

***

## Overview
Copilot-for-Consensus is designed to **scale institutional memory and accelerate decision-making** in technical communities like IETF working groups. It uses **LLM-powered summarization and insight extraction** to help participants keep up with mailing list traffic, track draft evolution, and identify consensus or dissent.

This project aims to be:
- **Containerized** for easy deployment.
- **Microservice-based** for modularity and scalability.
- **Deployable locally** using a lightweight micro-LLM or **in Azure Cloud** for enterprise-scale workloads.
- Built primarily in **Python** for accessibility and community contribution.

***

## Key Features (MVP)
- **Mailing List Ingestion:** Fetch archives via rsync or IMAP.
- **Parsing & Normalization:** Use Python `mailbox` or equivalent for structured extraction.
- **Summarization Engine:** Extractive + abstractive summaries powered by LLMs.
- **Consensus Detection:** Identify agreement/dissent signals in threads.
- **Draft Tracking:** Monitor mentions and evolution of RFC drafts.
- **Transparency:** Inline citations linking summaries to original messages.

***

## Long-Term Vision
Beyond summarization, Copilot-for-Consensus will evolve into an **interactive subject matter expert** that:
- **Understands RFCs and mailing list history** for deep contextual answers.
- Provides **semantic search and Q&A** across technical archives.
- Supports **multi-modal knowledge** (text, diagrams, code snippets).
- Offers **real-time collaboration tools** for chairs and contributors.
- Integrates with **standards governance workflows** for better decision tracking.

***

## License & Code Headers

This project is distributed under the **MIT License**. All files that support comments must include an SPDX license header:

```
SPDX-License-Identifier: MIT
Copyright (c) 2025 Copilot-for-Consensus contributors
```

**Header formats by file type:**
- **Python, Bash, YAML, Docker Compose:** Use `#` comments
  ```python
  # SPDX-License-Identifier: MIT
  # Copyright (c) 2025 Copilot-for-Consensus contributors
  ```
- **Markdown, HTML, XML:** Use `<!-- -->` comments
  ```html
  <!-- SPDX-License-Identifier: MIT
       Copyright (c) 2025 Copilot-for-Consensus contributors -->
  ```
- **JavaScript/TypeScript:** Use `//` comments
  ```typescript
  // SPDX-License-Identifier: MIT
  // Copyright (c) 2025 Copilot-for-Consensus contributors
  ```

All contributions must include appropriate SPDX headers. See [CONTRIBUTING.md](documents/CONTRIBUTING.md) for details.

***

## Architecture
- **Microservices:**  
