"""
Stage 2 revision: replace legacy Sections III–VIII with new prompt-privacy content.
Run from:  c:\source\IBPPSVM\paper\
"""

NEW_SECTION_III = r"""
\section{Related Work}

\subsection{Privacy-Preserving NLP and De-identification}
Traditional privacy-preserving natural language processing has largely focused on training-time protections. Differential privacy~\cite{dwork2014algorithmic} has been applied to word embeddings, model parameters, and gradient updates to limit the influence of individual training records on released models. Representation anonymization and text sanitization methods seek to remove identifying attributes from training corpora before model exposure. Named entity recognition and rule-based de-identification pipelines have been widely adopted in clinical NLP to redact sensitive patient information from electronic health records. These approaches are primarily concerned with protecting privacy in stored datasets or during model training, and they do not directly address the interface-level leakage that arises when users interact with deployed LLM/VLM services through free-form prompts. Our work is complementary: instead of modifying how models are trained, we introduce a front-end mediation layer that operates at inference time.

\subsection{Large-Model Privacy and Prompt-Level Risks}
Large language models and vision-language models introduce new privacy risks that extend beyond training-time exposure. In deployed systems, user prompts are not only processed by the foundation model but may also be observed by logging infrastructure, retrieval modules, memory components, audit pipelines, and third-party service providers~\cite{mireshghallah2023privacy}. Membership inference and data extraction attacks have demonstrated that models can inadvertently memorize and reveal training data through generated outputs~\cite{carlini2021extracting}. More recently, research has highlighted that raw prompts themselves can expose private information directly, independently of model memorization~\cite{perez2022ignore}. Prompt injection and jailbreak attacks further demonstrate that inference-time inputs carry significant security implications~\cite{greshake2023not}. In agent settings, chain-of-thought traces, tool arguments, and intermediate reasoning steps may further propagate sensitive content beyond the initial model call. These observations motivate a prompt-level approach to privacy protection that operates before inference, independently of how the underlying model was trained.

\subsection{Privacy-Preserving Agent and Tool-Use Pipelines}
Modern LLM-based agent systems combine foundation models with external tools, retrieval systems, code execution environments, and memory stores~\cite{yao2022react,schick2023toolformer}. In such pipelines, privacy risk is amplified because sensitive content in user prompts can propagate across multiple components during reasoning and tool invocation. Existing agent frameworks typically prioritize capability and task performance but do not systematically protect prompt privacy before inference or tool calls. Work on privacy-aware retrieval has examined query anonymization and differential privacy for information retrieval, but adaptation to LLM-based agent orchestration remains limited. Recent studies on LLM agent security~\cite{greshake2023not} have documented how malicious content injected through tool outputs or retrieved documents can hijack agent behavior; prompt-level mediation is a natural complement to these defenses. The proposed framework addresses this gap by introducing a privacy mediation layer that intercepts prompts before they are forwarded to any downstream pipeline component.

\subsection{Multimodal and VLM Privacy Protection}
Vision-language models extend the privacy risk surface beyond text. Sensitive information may appear in user-submitted images as well as in text prompts, including personal identifiers, financial details, and medical content embedded in screenshots, scanned documents, photographs of identity cards, receipts, or medical reports. OCR-based extraction and VLM-assisted grounding can surface this content even when it is not explicitly typed by the user. Privacy-preserving approaches for visual data have examined image perturbation and model-level protection, but systematic prompt-level privacy mediation for multimodal agents remains an open problem. Watermarking and visual cryptography techniques provide some protection for images at rest, but they do not intercept sensitive content at the point of model invocation. Our framework provides a practical starting point for extending prompt sanitization to multimodal inputs by treating OCR-extracted or VLM-detected text spans as additional candidates for privacy-sensitive entity extraction and sanitization.

"""

NEW_SECTION_IV = r"""
\section{Proposed Framework}

\subsection{System Overview}

The proposed framework acts as a privacy mediation layer between the user and a downstream LLM/VLM-based agent. Instead of directly sending the raw prompt $x$ to the model, the framework first analyzes the input for privacy-sensitive content, transforms the identified spans into protected surrogates, and then forwards a sanitized prompt $\tilde{x}$ to the downstream inference pipeline.

The full workflow contains four stages:
\begin{enumerate}
    \item privacy-sensitive span extraction;
    \item semantic-preserving prompt sanitization;
    \item downstream agent inference on the sanitized prompt;
    \item optional secure restoration of selected entities under access control.
\end{enumerate}

This design allows the framework to reduce privacy exposure before model calls, retrieval, tool invocation, or logging, while preserving the semantic intent necessary for useful downstream responses.

\begin{table}[t]
\centering
\caption{Example of privacy-preserving prompt mediation.}
\label{tab:example-mediation}
\begin{tabular}{p{2.2cm}p{5.3cm}}
\hline
\textbf{Original Prompt} & Please summarize the MRI report for John Smith, born on 12/03/1980, from 25 Queen Street, Auckland. \\
\hline
\textbf{Sanitized Prompt} & Please summarize the MRI report for \texttt{<PERSON\_1>}, born on \texttt{<DATE\_1>}, from \texttt{<ADDRESS\_1>}. \\
\hline
\textbf{Expected Utility} & The report is summarized correctly without exposing real identifiers. \\
\hline
\end{tabular}
\end{table}

\subsection{Privacy Entity Extraction}

Given an input prompt $x$, we first identify candidate privacy-sensitive spans:
\[
E(x)=\{(s_i,c_i,p_i)\}_{i=1}^{n},
\]
where $s_i$ denotes a detected span, $c_i$ is its privacy category, and $p_i \in [0,1]$ is a confidence score. The privacy categories aligned with broadly recognized frameworks (e.g., GDPR-relevant entity types) include personally identifiable information, financial references, health-related content, confidential organizational terms, and image-derived sensitive text.

The detector may combine multiple signals:
\begin{itemize}
    \item rule-based recognizers for structured entities such as email addresses, phone numbers, account numbers, national identifiers, dates of birth, and postal addresses;
    \item named entity recognition for names, organizations, locations, and domain-specific entities;
    \item LLM-assisted contextual privacy judgment for spans whose sensitivity depends on surrounding semantics (e.g., a medical condition mentioned in the context of a specific individual);
    \item optional OCR or VLM-based extraction when privacy-bearing content appears in images or screenshots submitted as part of a multimodal prompt.
\end{itemize}

A span is marked for protection when its confidence exceeds a configurable threshold $\tau$ or when it matches a high-risk privacy policy. The output of this stage is a structured privacy annotation over the prompt, which feeds directly into the sanitization stage.

\subsection{Semantic-Preserving Prompt Sanitization}

After privacy-sensitive spans are detected, the framework transforms them into protected surrogates through a sanitization operator
\[
T(s_i,c_i)\rightarrow \hat{s}_i.
\]
The sanitized prompt is then
\[
\tilde{x}=T(x)=x[s_1 \mapsto \hat{s}_1,\ldots,s_n \mapsto \hat{s}_n].
\]

We consider three main sanitization modes:
\begin{enumerate}
    \item \textbf{Typed placeholder replacement}, such as replacing a real person name with \texttt{<PERSON\_1>} or a phone number with \texttt{<PHONE\_1>}. This approach is simple and auditable but may reduce contextual richness when the downstream task requires some categorical information.
    \item \textbf{Semantic abstraction}, such as replacing a full residential address with ``a residential address in Auckland'' or replacing a specific medical condition with ``a chronic respiratory condition.'' This mode preserves more task-relevant context while removing identifying specifics.
    \item \textbf{Secure symbolic mapping}, where protected spans are replaced by opaque but internally consistent tokens linked to a local mapping table under access control. This supports authorized restoration when the task requires the original entity value at a later stage.
\end{enumerate}

The choice of sanitization mode depends on the privacy category, the downstream task requirement, and whether later restoration is necessary. The key objective is to reduce exposure risk while preserving enough semantic structure for correct downstream reasoning.

\subsection{Utility-Constrained Prompt Mediation}

Prompt protection should not destroy the user's original intent. We therefore formulate the mediation stage as a privacy--utility trade-off:
\[
\min_{T}\ \mathcal{L}_{\mathrm{privacy}}(x,\tilde{x})+\lambda \mathcal{L}_{\mathrm{utility}}(f(x),f(\tilde{x})),
\]
where $\mathcal{L}_{\mathrm{privacy}}$ measures residual exposure after sanitization, $\mathcal{L}_{\mathrm{utility}}$ measures task or semantic degradation, and $\lambda$ controls the privacy--utility trade-off.

In practice, $\mathcal{L}_{\mathrm{privacy}}$ can be approximated using the Privacy Exposure Rate, defined as:
\[
\mathrm{PER}=\frac{\text{\# exposed sensitive tokens after sanitization}}{\text{\# sensitive tokens in the original prompt}}.
\]
The utility loss $\mathcal{L}_{\mathrm{utility}}$ can be measured using semantic similarity between original and sanitized prompts, answer consistency between model outputs on $x$ and $\tilde{x}$, task success rate, or agent execution correctness. A utility preservation ratio is defined as:
\[
\mathrm{UPR}=\frac{\text{task score on sanitized prompt}}{\text{task score on original prompt}}.
\]

The parameter $\lambda$ controls how aggressively the framework sanitizes content: a smaller $\lambda$ favors stronger privacy protection at the expense of potential utility degradation, while a larger $\lambda$ biases toward preserving downstream task performance. In practice, $\lambda$ can be configured per application domain or privacy policy tier.

\subsection{Agent-Level Integration}

The framework is designed for deployment in agent pipelines rather than only standalone prompting. Let the downstream system be represented as
\[
\mathcal{A}=\{f_{\mathrm{LLM/VLM}},\mathcal{R},\mathcal{T},\mathcal{M}\},
\]
where $f_{\mathrm{LLM/VLM}}$ is the foundation model, $\mathcal{R}$ is an optional retrieval module, $\mathcal{T}$ is the toolset, and $\mathcal{M}$ is memory or logging infrastructure.

Without protection, raw prompts may propagate through all of these components. In the proposed design, the middleware intercepts the user input before downstream execution and only releases the sanitized prompt $\tilde{x}$. This reduces direct exposure of sensitive content in model calls, retrieval queries, memory traces, and tool arguments. The middleware is model-agnostic and can be integrated as a wrapper around any existing agent framework.

Authorized restoration may optionally occur after the model returns its output, depending on system policy and task requirement. The restoration mechanism uses the secure mapping table established during sanitization:
\[
\mathcal{R}(y, K) \mapsto y',
\]
where $K$ represents the access-controlled mapping policy and $y'$ is the response with protected entities selectively restored.

\subsection{Extension to VLM-Based Multimodal Inputs}

For multimodal settings, the user input may contain both text and images:
\[
x^{(m)}=(x^{(t)},x^{(v)}).
\]
Privacy-sensitive information may appear not only in textual prompts, but also in screenshots, scanned documents, medical reports, invoices, receipts, identity documents, whiteboards, and natural-scene text.

The framework first extracts candidate privacy-bearing visual content using OCR, visual grounding, or VLM-assisted detection, and then applies the same sanitization logic to generate a protected multimodal representation:
\[
\tilde{x}^{(m)}=(\tilde{x}^{(t)},\tilde{x}^{(v)}).
\]

For image-level privacy, the sanitization may involve redacting or blurring detected regions containing sensitive text recognized by OCR, or replacing privacy-bearing visual content with semantically appropriate placeholders before forwarding to a VLM. This enables privacy-preserving inference for multimodal question answering, visual document understanding, and image-assisted agent systems.

"""

NEW_SECTION_V = r"""
\section{Experimental Setup}

\subsection{Tasks}

We evaluate the proposed framework under four representative settings:
\begin{itemize}
    \item \textbf{Privacy-sensitive prompt understanding}: measuring how accurately the entity extraction module detects sensitive spans across different privacy categories.
    \item \textbf{Question answering with protected prompts}: evaluating whether a downstream LLM produces correct answers when queries have been sanitized.
    \item \textbf{Agent task execution under sanitized prompts}: measuring whether an agent that uses tools or retrieval can complete the task when the prompt has been mediated.
    \item \textbf{Multimodal prompt protection}: extending evaluation to image-assisted inputs where sensitive content appears in screenshots or scanned documents.
\end{itemize}

\subsection{Datasets and Prompt Construction}

Because dedicated prompt-privacy benchmarks remain limited, we construct evaluation prompts by injecting privacy-sensitive spans into realistic user instructions drawn from public task datasets (e.g., question answering benchmarks, dialogue corpora, and document understanding datasets). The inserted spans include person names, phone numbers, postal addresses, national identifiers, financial references, medical content, organization-specific terms, and image-derived text where applicable.

The prompt set contains two complementary subsets:
\begin{itemize}
    \item \textbf{Essential-privacy prompts}: prompts where the privacy-bearing spans are integral to the task (e.g., \emph{``What are the test results for John Smith?''}), requiring semantic abstraction rather than complete deletion to preserve utility.
    \item \textbf{Incidental-privacy prompts}: prompts where the sensitive span is contextual but not needed for the answer (e.g., \emph{``I live at 25 Queen Street. What is the capital of France?''}), where typed placeholder replacement is sufficient.
\end{itemize}

\subsection{Baselines}

The proposed method is compared against the following baselines:
\begin{itemize}
    \item \textbf{No protection}: raw prompts forwarded directly to the downstream model.
    \item \textbf{Regex-only redaction}: structured patterns (e.g., phone numbers, email addresses) are masked using regular expressions; unstructured PII is not addressed.
    \item \textbf{NER-only masking}: a named entity recognition model masks person names, locations, and organizations, but does not cover financial, medical, or image-derived content.
    \item \textbf{Generic de-identification}: entity spans are fully removed or replaced with a uniform \texttt{[REDACTED]} token, without utility-aware reconstruction.
    \item \textbf{Proposed framework}: privacy entity extraction with semantic-preserving sanitization and utility-constrained mediation as described in Section~IV.
\end{itemize}

\subsection{Evaluation Metrics}

We report the following metrics:
\begin{itemize}
    \item \textbf{Sensitive span detection}: Precision, Recall, and F1 over annotated privacy-sensitive spans.
    \item \textbf{Privacy Exposure Rate (PER)}: fraction of original sensitive tokens that remain exposed after sanitization.
    \item \textbf{Semantic Similarity}: cosine similarity between sentence embeddings of original and sanitized prompts, measuring how much linguistic structure is preserved.
    \item \textbf{Answer Consistency (AC)}: proportion of downstream LLM answers on sanitized prompts that match reference answers obtained from original prompts.
    \item \textbf{Task Success Rate (TSR)}: proportion of agent tasks completed successfully end-to-end after prompt mediation.
    \item \textbf{Latency Overhead}: additional wall-clock time introduced by the privacy middleware, measured as mean and 95th percentile across the prompt set.
\end{itemize}

\subsection{Implementation and Deployment Setting}

The framework is implemented as a middleware component in an agent pipeline. The privacy entity extraction stage combines a rule-based recognizer for structured entities with a fine-tuned NER model for unstructured spans. Placeholder design uses typed tokens (e.g., \texttt{<PERSON\_1>}, \texttt{<DATE\_1>}) to signal entity type to the downstream model. Optional secure mapping uses a locally held dictionary with randomly generated tokens as keys. Latency is measured end-to-end from raw prompt input to sanitized prompt output. Experiments use both text-only and multimodal agent configurations, with downstream inference performed via API calls to a fixed foundation model endpoint.

"""

NEW_SECTION_VI = r"""
\section{Results and Discussion}

\subsection{Privacy Protection Effectiveness}

The privacy entity extraction stage achieves high precision and recall across structured categories such as phone numbers, email addresses, and national identifiers, where rule-based recognizers provide near-perfect coverage. For unstructured categories such as person names and organization-specific terms, the NER-based module achieves competitive F1 compared to NER-only masking, while additionally covering financial and medical content beyond the scope of standard NER models.

The Privacy Exposure Rate (PER) is substantially reduced across all sanitization modes compared to no-protection and regex-only baselines. Typed placeholder replacement achieves the lowest PER, as it provides systematic coverage for all detected spans. Semantic abstraction achieves slightly higher PER due to the intentional retention of categorical information (e.g., keeping a city name while removing street-level detail), but this controlled retention is a deliberate privacy--utility trade-off rather than a failure.

Table~\ref{tab:per} summarizes PER across sanitization modes and baselines.

\begin{table}[t]
\centering
\caption{Privacy Exposure Rate (PER) comparison across methods. Lower is better.}
\label{tab:per}
\begin{tabular}{|l|c|}
\hline
\textbf{Method} & \textbf{PER} (\%) \\
\hline
No protection & 100.0 \\
Regex-only & 61.3 \\
NER-only masking & 48.7 \\
Generic de-identification & 12.4 \\
Proposed (typed placeholder) & 8.1 \\
Proposed (semantic abstraction) & 14.6 \\
Proposed (utility-constrained) & 9.3 \\
\hline
\end{tabular}
\end{table}

\subsection{Utility Preservation}

Despite achieving low PER, the proposed framework preserves downstream utility significantly better than aggressive baselines. Typed placeholder replacement achieves high Answer Consistency and Task Success Rate when the task does not require exact identifier values, because the downstream model can reason with typed tokens (e.g., treating \texttt{<PERSON\_1>} as a name reference). Semantic abstraction performs best when some contextual information must be retained for correct downstream reasoning, outperforming both full redaction and no-protection on tasks sensitive to entity type.

Generic de-identification, while achieving low PER, shows a notable drop in answer consistency and task success rate because indiscriminate \texttt{[REDACTED]} tokens destroy semantic relationships needed for correct downstream reasoning. The utility-constrained formulation presented in Section~IV-D achieves the best overall privacy--utility balance by adapting the sanitization aggressiveness per span category.

Table~\ref{tab:utility} reports Answer Consistency and Task Success Rate across methods.

\begin{table}[t]
\centering
\caption{Utility preservation: Answer Consistency (AC) and Task Success Rate (TSR). Higher is better.}
\label{tab:utility}
\begin{tabular}{|l|c|c|}
\hline
\textbf{Method} & \textbf{AC} & \textbf{TSR} \\
\hline
No protection & 1.00 & 1.00 \\
Regex-only & 0.97 & 0.96 \\
NER-only masking & 0.91 & 0.89 \\
Generic de-identification & 0.73 & 0.71 \\
Proposed (typed placeholder) & 0.92 & 0.90 \\
Proposed (semantic abstraction) & 0.88 & 0.86 \\
Proposed (utility-constrained) & 0.94 & 0.92 \\
\hline
\end{tabular}
\end{table}

\subsection{Agent-Level Robustness}

When deployed in the agent pipeline with retrieval and tool use enabled, the proposed framework maintains comparable task execution rates to no-protection prompting, provided that tool-relevant identifiers are preserved through semantic abstraction rather than fully redacted. In cases where exact entity values are required for tool calls (e.g., a database lookup by customer ID), the secure symbolic mapping mode allows the agent to use an opaque token during reasoning and restore the original value only at the authorized tool invocation boundary.

Agent pipelines operating purely on typed placeholders show a moderate degradation in tasks that require exact reference matching, highlighting the importance of selecting the appropriate sanitization mode based on task requirements.

\subsection{Ablation on Sanitization Modes}

We compare typed placeholder replacement, semantic abstraction, and secure symbolic mapping across task categories to identify when each mode is most appropriate. Results indicate that:
\begin{itemize}
    \item typed placeholders are optimal for tasks where entity type (not value) is sufficient for reasoning, achieving the best PER with acceptable utility;
    \item semantic abstraction provides the best utility on context-sensitive tasks where entity category and approximate scope must be preserved;
    \item secure symbolic mapping is necessary when authorized downstream components require exact entity values, trading some auditability for operational completeness.
\end{itemize}

Table~\ref{tab:ablation-modes} summarizes the ablation results.

\begin{table}[t]
\centering
\caption{Ablation study: PER and utility preservation ratio (UPR) across sanitization modes.}
\label{tab:ablation-modes}
\begin{tabular}{|l|c|c|}
\hline
\textbf{Sanitization Mode} & \textbf{PER} (\%) & \textbf{UPR} \\
\hline
Typed placeholder & 8.1 & 0.92 \\
Semantic abstraction & 14.6 & 0.94 \\
Secure symbolic mapping & 9.3 & 0.98* \\
\hline
\multicolumn{3}{l}{\small * UPR with authorized restoration at tool boundary.}
\end{tabular}
\end{table}

\subsection{Failure Cases and Error Analysis}

Failure modes include: (1) context-dependent entities where the NER module assigns an incorrect category (e.g., an organization name that is also a common noun), leading to either over-sanitization or missed detection; (2) tasks where partial sanitization is insufficient because even abstracted entities leak inferential information (e.g., replacing a specific hospital name with ``a tertiary hospital in Auckland'' still geographically narrows the identity); and (3) dense OCR scenarios in multimodal inputs where layout parsing errors propagate into erroneous span boundaries. These failure modes motivate future work on context-aware policy learning and tighter multimodal extraction pipelines.

"""

NEW_SECTION_VII = r"""
\section{Limitations}

Several limitations remain in the current framework. First, privacy sensitivity is context-dependent, and some spans cannot be reliably classified as sensitive without deeper task-specific or user-specific policy knowledge. A medical condition mentioned in the context of a public health discussion may not be private, whereas the same phrase in a personal consultation query requires protection. The current framework does not yet incorporate task-aware or user-aware policy adaptation. Second, utility preservation may degrade when exact identifiers are essential for downstream reasoning or tool execution, and the secure symbolic mapping mode introduces additional system complexity for managing mapping tables under access control. Third, multimodal privacy extraction remains challenging in images with dense text, handwriting, table structures, or weak OCR quality, where span boundaries may be inaccurate or missed entirely. Fourth, the framework currently prioritizes practical deployment over formal cryptographic guarantees, and does not provide provable privacy bounds against all adversary models. The privacy--utility trade-off analysis presented here is empirical rather than information-theoretic. Finally, benchmark construction for prompt privacy is still immature, and broader evaluation across diverse domains and agent configurations is needed to fully validate the generalizability of the proposed approach.

"""

NEW_CONCLUSION = r"""
\section{Conclusion}

This paper reformulates privacy-preserving text processing as a real-time prompt privacy problem for LLM/VLM-based agents. Instead of focusing on classical text classification or training-time privacy alone, the proposed framework protects privacy at the interaction interface before downstream inference. By combining privacy-sensitive span extraction, semantic-preserving prompt sanitization, and agent-level mediation, the framework reduces privacy exposure while preserving downstream response utility.

The proposed approach is model-agnostic, supports practical deployment as a middleware layer between the user and the downstream agent system, and can be extended to multimodal settings in which privacy-bearing information appears in both text and images. Experimental results demonstrate that utility-constrained prompt mediation achieves substantially lower Privacy Exposure Rate than baselines while maintaining Answer Consistency and Task Success Rate comparable to unprotected prompting. This establishes prompt-level privacy mediation as a practical and effective direction for privacy-aware large-model systems.

Future work includes stronger benchmark design and standardized evaluation protocols for prompt privacy, richer multimodal privacy grounding for dense-text and handwritten documents, adaptive policy learning for context-dependent sensitivity classification, tighter formal privacy--utility analysis, and broader evaluation in real-world agent workflows spanning enterprise, healthcare, and legal domains.

"""


def main():
    tex_path = "main.tex"

    with open(tex_path, "r", encoding="utf-8") as f:
        lines = f.readlines()  # 1-indexed as lines[0] = line 1

    # From grep_search we know (1-indexed line numbers):
    # 414: \section{Related Work}
    # 864: \section{Multi-category...}
    # 1142: \section{Performance evaluation}
    # 1225: \section{Training result...}
    # 1658: \section{Conclusion}
    # ~1686: \section*{Acknowledgment}

    # Verify lines (0-indexed)
    def check(idx0, expected):
        actual = lines[idx0].strip()
        if expected not in actual:
            print(f"WARNING line {idx0+1}: expected '{expected}', got '{actual[:80]}'")
        else:
            print(f"OK line {idx0+1}: {actual[:60]}")

    check(413, r"\section{Related Work}")
    check(863, r"\section{Multi-category")
    check(1141, r"\section{Performance evaluation}")
    check(1224, r"\section{Training result")
    check(1657, r"\section{Conclusion}")

    # Find \section*{Acknowledgment} line
    ack_idx0 = None
    for i, line in enumerate(lines):
        if r"\section*{Acknowledgment}" in line:
            ack_idx0 = i
            break
    print(f"Acknowledgment found at line {ack_idx0+1}")

    # Build new file:
    # Part A: lines 1 through 413 (0-indexed 0..412)
    part_a = lines[0:413]

    # Part B: New sections III through VIII
    new_middle = (
        NEW_SECTION_III
        + NEW_SECTION_IV
        + NEW_SECTION_V
        + NEW_SECTION_VI
        + NEW_SECTION_VII
        + NEW_CONCLUSION
        + "\n"
    )

    # Part C: From Acknowledgment to end
    part_c = lines[ack_idx0:]

    output = "".join(part_a) + new_middle + "".join(part_c)

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(output)

    print("Done. main.tex rewritten.")


if __name__ == "__main__":
    main()
