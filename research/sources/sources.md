# Sources

Collected manually + some suggested by AI, summaries provided by AI

## In spec

### Bishop & Bishop (2023) - Deep Learning: Foundations and Concepts. Springer

- Link: [https://link.springer.com/book/10.1007/978-3-031-45468-4](https://link.springer.com/book/10.1007/978-3-031-45468-4)
- Type: Book (textbook)
- Summary: Clear, maths-first explanation of how modern deep learning models learn and generalize. Provides the theory needed to explain detector confidence scores, threshold choices, and model family selection.
- Use in thesis: Background on models and embeddings. Justify confidence thresholds and weighting in the rule engine. Frame error analysis with bias-variance language.

### Rothman (2024) - Transformers for Natural Language Processing and Computer Vision. Packt

- Link: Not available for free :(
- Type: Book (practitioner guide)
- Summary: Hands-on cookbook showing how to wire, prompt, and tune Transformer and multimodal models. Helpful when turning design ideas for STYLE, CONTENT, or CUSTOM detectors into quick prototypes.
- Use in thesis: Implementation. Cite only for practical setup, not for core scientific claims.

### Zesch et al. (2023) - To Score or Not to Score: Factors Influencing Performance and Feasibility of Automatic Content Scoring of Text Responses. Educational Measurement: Issues & Practice

- Link: [https://onlinelibrary.wiley.com/doi/10.1111/emip.12544](https://onlinelibrary.wiley.com/doi/10.1111/emip.12544)
- Type: Journal article
- Summary: Shows that clear rubrics, enough text length, and consistent human raters drive scoring quality more than fancy models. Sets expectations for what good agreement looks like.
- Use in thesis: Related work on what affects scoring quality. Justify using several metrics (Quadratic Weighted Kappa agreement, mean absolute error, correlation, intra class correlation). Discuss limits when moving between IFJ and IPP tasks or years.

### Bevilacqua et al. (2025) - When Automated Assessment Meets Automated Content Generation: Examining Text Quality in the Era of GPTs. ACM TOIS

- Link: [https://dl.acm.org/doi/10.1145/3702639](https://dl.acm.org/doi/10.1145/3702639)
- Type: Journal article
- Summary: Finds polished AI text can look better than genuine student writing and get over-scored if unchecked.
- Use in thesis: Risks and ethics. Motivate human review for edge cases. Support showing evidence snippets for transparency.

## Others

### Chang et al. (2024) - A Survey on Evaluation of Large Language Models. ACM Computing Surveys

- Link: [https://dl.acm.org/doi/10.1145/3641289](https://dl.acm.org/doi/10.1145/3641289)
- Type: Journal survey article
- Summary: Survey of how to properly test LLMs and avoid shaky claims: vary prompts, report uncertainty, check for data leakage.
- Use: Evaluation design (prompt robustness runs). Reporting (confidence intervals, multiple seeds). Reproducibility checklist items.

### Huang et al. (2022) - LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking. ACM MM'22

- Link: [https://arxiv.org/abs/2204.08387](https://arxiv.org/abs/2204.08387)
- Type: Conference paper (ACM MM)
- Summary: Multimodal model that learns text and layout together, showing a path beyond simple PDF heuristics.
- Use: Related work on layout-aware backbones. Justify possible future upgrade of diagram/table detectors. Explain current heuristic limitations.

### Schaller et al. (2024) - Fairness in Automated Essay Scoring: A Comparative Analysis of Algorithms on German Learner Essays. BEA (ACL workshop)

- Link: [https://aclanthology.org/2024.bea-1.18/](https://aclanthology.org/2024.bea-1.18/)
- Type: Workshop paper (ACL BEA)
- Summary: Provides a concrete checklist for fairness: compare errors across language learner groups and report gaps.
- Use: Fairness section protocol. Risk analysis for non‑native style penalties. Per‑language error gap reporting.

### PubLayNet (2019) - Largest dataset for document layout analysis

- Link: [https://arxiv.org/abs/1908.07836](https://arxiv.org/abs/1908.07836)
- Type: Dataset (layout)
- Summary: Massive dataset for training layout models at scale. Shows what data volume a strong layout model can leverage.
- Use: Future work data source. Motivation for switching from heuristics to pretrained layout detection.

### DocLayNet (2022) - Human-annotated dataset for diverse document layouts

- Link: [https://arxiv.org/abs/2206.01062](https://arxiv.org/abs/2206.01062)
- Type: Dataset (layout, human annotated)
- Summary: High-quality, diverse layout labels highlighting that models trained elsewhere might not fully match student reports.
- Use: Threats to validity (domain shift). Motivate testing on in‑house IFJ/IPP docs.

### Kim et al. (2022) - Donut: OCR-Free Document Understanding Transformer. ECCV

- Link: [https://arxiv.org/abs/2111.15664](https://arxiv.org/abs/2111.15664)
- Type: Conference paper (ECCV)
- Summary: Shows an end-to-end model can skip OCR and avoid cascading errors while being faster.
- Use: Architecture trade‑offs section (current pipeline vs unified model). Cost and latency discussion.

### IJCAI (2024) - Automated Essay Scoring: Recent Successes and Future Directions

- Link: [https://www.ijcai.org/proceedings/2024/897](https://www.ijcai.org/proceedings/2024/897)
- Type: Conference survey paper (IJCAI)
- Summary: Quick overview of how essay scoring methods evolved and what problems (fairness, robustness) remain.
- Use: Related work bridge into your hybrid rule + detector setup. Motivate focus on fairness and explanations.

### Doewes et al. (2023) - Evaluating Quadratic Weighted Kappa as the Standard Performance Metric for automated essay scoring. EDM

- Link: [https://educationaldatamining.org/EDM2023/proceedings/2023.EDM-long-papers.9/index.html](https://educationaldatamining.org/EDM2023/proceedings/2023.EDM-long-papers.9/index.html)
- Type: Conference paper (EDM)
- Summary: Explains why Quadratic Weighted Kappa alone can mislead when classes are imbalanced and argues for extra metrics.
- Use: Justify multi‑metric reporting. Note validity risks when Quadratic Weighted Kappa looks high on skewed data.

### Quah et al. (2024) - Reliability of ChatGPT in Automated Essay Scoring. BMC Medical Education

- Link: [https://bmcmededuc.biomedcentral.com/articles/10.1186/s12909-024-05881-6](https://bmcmededuc.biomedcentral.com/articles/10.1186/s12909-024-05881-6)
- Type: Journal article (medical education)
- Summary: Finds LLM agreement depends strongly on clear rubrics and highlights where it drifts from human judgment.
- Use: Design of human vs model agreement study. Limitations section on rubric ambiguity.

### Artetxe et al. (2023) - Revisiting Machine Translation for Cross-Lingual Classification. EMNLP

- Link: [https://aclanthology.org/2023.emnlp-main.399/](https://aclanthology.org/2023.emnlp-main.399/)
- Type: Conference paper (EMNLP)
- Summary: Shows simple translate-then-classify can match multilingual models in many tasks.
- Use: Justify chosen multilingual strategy (translation vs direct embeddings) for LANG and TERM detectors.

### Feng et al. (2020/2022) - LaBSE: Language-agnostic BERT Sentence Embedding

- Link: [https://arxiv.org/abs/2007.01852](https://arxiv.org/abs/2007.01852)
- Type: Preprint + conference paper (ACL)
- Summary: Offers out-of-the-box multilingual sentence vectors good for fast similarity and language checks.
- Use: Implementation backbone for LANG and TERM detectors. Baseline for cross‑lingual tests.

### Adhikari & Agarwal (2024) - A Comparative Study of PDF Parsing Tools Across Diverse Document Categories. arXiv

- Link: [https://arxiv.org/abs/2410.09871](https://arxiv.org/abs/2410.09871)
- Type: Preprint (tool comparison)
- Summary: Benchmarks several PDF parsers across document types. Shows trade offs in text fidelity, table and figure extraction, and speed. Supports an informed PDF to Markdown pipeline choice.
- Use: Parser choice justification. Performance section (runtime vs extraction quality).

### Guo et al. (2025) - Artificial Intelligence Bias on English Language Learners in Automatic Scoring. arXiv

- Link: [https://arxiv.org/abs/2505.10643](https://arxiv.org/abs/2505.10643)
- Type: Preprint (fairness/bias)
- Summary: Finds small or imbalanced language groups can exaggerate bias numbers.
- Use: Fairness protocol (stratified splits). Limitations (sample size imbalance).

### Bishop (2006) - Pattern Recognition and Machine Learning. Springer

- Link: [https://link.springer.com/book/10.1007/978-0-387-45528-0](https://link.springer.com/book/10.1007/978-0-387-45528-0)
- Type: Book (textbook)
- Summary: Classic probabilistic pattern recognition text (graphical models, EM, Bayesian inference) grounding uncertainty handling and calibration concepts still relevant for detector confidence interpretation.
- Use: Deeper theoretical backup for confidence calibration, probabilistic reasoning in rule engine extensions, background chapter cross-reference with newer Bishop & Bishop (2023).

### State-of-the-Art Model Architectures for Document Layout Analysis

- Link: [https://www.rohan-paul.com/p/state-of-the-art-model-architectures](https://www.rohan-paul.com/p/state-of-the-art-model-architectures)
- Type: Web article (survey-style synthesis)
- Summary: Outlines DLA goals and challenges. Traces shift from rule systems to CNN, Transformer, multimodal, and GNN models. Lists key model families (DETR/DINO, DiT, LayoutLM, VGT, GLAM, hybrids) and benchmark gap between PubLayNet and DocLayNet. Notes robustness and domain shift as active issues.
- Use: Roadmap support for staged upgrade (heuristics -> light detector/GNN -> multimodal). Motivation for reporting robustness and domain generalization metrics. Source for ensemble justification.

### Human versus Machine: The Effectiveness of ChatGPT in Automated Essay Scoring (2025)

- Link: [https://www.tandfonline.com/doi/epdf/10.1080/14703297.2025.2469089](https://www.tandfonline.com/doi/epdf/10.1080/14703297.2025.2469089)
- Type: Journal article (large language model vs human scoring study)
- Summary: Compares ChatGPT 3.5 and 4 to human raters on authentic student work. Reports agreement and variance gaps and notes model leniency patterns. Shows current large language models do not yet match consistent human scoring.
- Use: Evaluation section citation for multi rater agreement (Quadratic Weighted Kappa, intra class correlation). Justifies confidence calibration checks and a human review loop when considering an optional large language model baseline.
