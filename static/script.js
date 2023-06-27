document
  .getElementById("translation-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();

    const sourceLang = document.getElementById("source-lang").value;
    const targetLang = document.getElementById("target-lang").value;
    const fileInput = document.getElementById("file-upload");
    const translatorName = document.getElementById("translator-name").value;
    const file = fileInput.files[0];

    if (!file) {
      alert("Please upload a document.");
      return;
    }

    const formData = new FormData();
    formData.append("source_lang", sourceLang);
    formData.append("target_lang", targetLang);
    formData.append("file", file);
    formData.append("translator_name", translatorName);

    const response = await fetch("/translate", {
      method: "POST",
      body: formData,
    });

    if (response.ok) {
      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `translated_${file.name}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      const errorData = await response.json();
      alert(errorData.error);
    }
  });
  