const uploadForm = document.getElementById("upload-form");
const questionForm = document.getElementById("question-form");
const fileInput = document.getElementById("file-input");
const questionInput = document.getElementById("question-input");
const uploadStatus = document.getElementById("upload-status");
const questionStatus = document.getElementById("question-status");
const uploadButton = document.getElementById("upload-button");
const askButton = document.getElementById("ask-button");
const answerContainer = document.getElementById("answer-container");
const answerText = document.getElementById("answer-text");
const sourcesContainer = document.getElementById("sources-container");
const sourcesList = document.getElementById("sources-list");

const API_BASE = (() => {
    if (window.APP_CONFIG?.apiBase) {
        return window.APP_CONFIG.apiBase.replace(/\/$/, "");
    }

    const origin = window.location.origin;
    if (origin && origin.startsWith("http") && origin !== "null") {
        return origin;
    }

    return "https://docs-agentic-ai.onrender.com";
})();

const apiUrl = path => {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${API_BASE}${normalized}`;
};

let documentReady = false;

askButton.disabled = true;

const STATUS_CLASSNAMES = ["status--info", "status--success", "status--error"];

function setStatus(element, message, level = "info") {
    element.textContent = message;
    STATUS_CLASSNAMES.forEach(className => element.classList.remove(className));
    element.classList.add(`status--${level}`);
}

function resetAnswer() {
    answerContainer.classList.add("hidden");
    sourcesContainer.classList.add("hidden");
    answerText.textContent = "";
    sourcesList.innerHTML = "";
}

uploadForm.addEventListener("submit", async event => {
    event.preventDefault();

    const file = fileInput.files[0];
    if (!file) {
        setStatus(uploadStatus, "Please choose a document before processing.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setStatus(uploadStatus, "Processing document... This may take 1-2 minutes for large PDFs.", "info");
    resetAnswer();
    uploadButton.disabled = true;
    uploadButton.textContent = "Processing...";
    askButton.disabled = true;

    try {
        const response = await fetch(apiUrl("/api/upload"), {
            method: "POST",
            body: formData,
        });

        const data = await response.json();
        if (!response.ok) {
            const message = data.error || "Failed to process the document.";
            setStatus(uploadStatus, message, "error");
            documentReady = false;
            return;
        }

        documentReady = true;
        setStatus(uploadStatus, data.message || "Document processed successfully.", "success");
        setStatus(questionStatus, "Document ready. Ask your question.", "info");
        askButton.disabled = false;
    } catch (error) {
        console.error(error);
        setStatus(uploadStatus, "Unexpected error while uploading the file.", "error");
        documentReady = false;
    } finally {
        uploadButton.disabled = false;
        uploadButton.textContent = "Process Document";
    }
});

questionForm.addEventListener("submit", async event => {
    event.preventDefault();

    if (!documentReady) {
        setStatus(questionStatus, "Please upload and process a document first.", "error");
        return;
    }

    const question = questionInput.value.trim();
    if (!question) {
        setStatus(questionStatus, "Please enter a question.", "error");
        return;
    }

    setStatus(questionStatus, "Generating answer...", "info");
    askButton.disabled = true;

    try {
        const response = await fetch(apiUrl("/api/ask"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });

        if (!response.ok) {
            const data = await response.json();
            const message = data.error || "Failed to retrieve an answer.";
            setStatus(questionStatus, message, "error");
            resetAnswer();
            return;
        }

        // Handle Server-Sent Events (SSE) streaming
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let answerTextContent = "";
        let buffer = "";

        const processEvent = rawEvent => {
            const eventLines = rawEvent.split(/\r?\n/);
            const dataLines = [];
            for (const line of eventLines) {
                if (line.startsWith("data:")) {
                    dataLines.push(line.slice(5).trimStart());
                }
            }

            if (dataLines.length === 0) {
                return;
            }

            const payload = dataLines.join("\n").trim();
            if (!payload) {
                return;
            }

            try {
                const data = JSON.parse(payload);

                if (data.type === "token") {
                    answerTextContent += data.content;
                    answerText.textContent = answerTextContent;
                } else if (data.type === "sources") {
                    sourcesList.innerHTML = "";
                    const sources = data.sources || [];
                    if (sources.length === 0) {
                        const item = document.createElement("li");
                        item.textContent = "No supporting sources returned.";
                        sourcesList.appendChild(item);
                    } else {
                        sources.forEach(source => {
                            const item = document.createElement("li");
                            const title = document.createElement("div");
                            title.className = "source-title";
                            title.textContent = source.source || "Unknown source";

                            const snippet = document.createElement("div");
                            snippet.className = "source-snippet";
                            snippet.textContent = truncateText(source.content || "", 360);

                            item.appendChild(title);
                            item.appendChild(snippet);
                            sourcesList.appendChild(item);
                        });
                    }
                    sourcesContainer.classList.remove("hidden");
                } else if (data.type === "done") {
                    setStatus(questionStatus, "Answer ready.", "success");
                } else if (data.type === "error") {
                    setStatus(questionStatus, data.message, "error");
                }
            } catch (parseError) {
                console.error("JSON parse error:", parseError, "Event:", payload);
            }
        };
        
        answerContainer.classList.remove("hidden");
        answerText.textContent = "";
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });

            let eventBoundary;
            while ((eventBoundary = buffer.indexOf("\n\n")) !== -1) {
                const rawEvent = buffer.slice(0, eventBoundary);
                buffer = buffer.slice(eventBoundary + 2);
                processEvent(rawEvent);
            }
        }

        if (buffer.trim()) {
            processEvent(buffer);
        }
    } catch (error) {
        console.error(error);
        setStatus(questionStatus, "Unexpected error while retrieving the answer.", "error");
        resetAnswer();
    } finally {
        askButton.disabled = false;
    }
});

function truncateText(text, maxLength) {
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength).trim()}...`;
}
