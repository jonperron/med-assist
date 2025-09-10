# 🩺 Med-Assist

[![Build Status](https://img.shields.io/github/actions/workflow/status/jonperron/med-assist/backend-ci.yml?branch=main)](https://github.com/your-org/med-assist/actions)

**Med-Assist** is an open-source tool that helps medical professionals extract key information—such as diseases, symptoms, and treatments—from clinical documents.

---

## ⚠️ Disclaimer

> **Med-Assist is under active development.**
It is not intended for use in clinical decision-making and should not replace professional medical advice or diagnosis.

---

## 🔐 Privacy & Data Control

- **Local-first by design**
  Med-Assist runs entirely on your infrastructure—no external APIs or cloud dependencies.

- **Secure storage**
  All data is stored in a local Redis instance, ensuring patient information remains private and compliant with data protection regulations.

---

## 🌱 Green Impact

Med-Assist is built to run on minimal hardware, with a small footprint. It’s optimized to reduce energy usage and maximize sustainability—making it ideal for edge devices or local hospital servers.

---

## 🧩 Project Structure

- [`backend/`](./backend/README.md) – FastAPI-based backend for processing and text extraction.
- [`frontend/`](./frontend/README.md) – Web interface to upload, manage, and visualize documents.

---

## 🤝 Contributing

We welcome community contributions!

---

## 📜 License

This project is licensed under the **Apache 2.0 License**.

---

## 📚 References

This project builds upon the following resources:

- Labrak, Y., Bazoge, A., Dufour, R., Rouvier, M., Morin, E., Daille, B., & Gourraud, P.-A. (2023).
  **DrBERT: A Robust Pre-trained Model in French for Biomedical and Clinical domains.**
  *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL'23), Long Paper*, Toronto, Canada.
  [ACL Anthology](https://aclanthology.org/)

- Grabar, N., Dalloux, C., & Claveau, V. (2020).
  **CAS: corpus of clinical cases in French.**
  *Journal of Biomedical Semantics, 11*, 7.
  [https://doi.org/10.1186/s13326-020-00225-x](https://doi.org/10.1186/s13326-020-00225-x)
