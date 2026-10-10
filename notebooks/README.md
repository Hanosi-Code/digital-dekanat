# Colab-ноутбуки

Здесь эксперименты, которые не входят в рантайм бота:
сравнение OCR-движков, подбор порогов предобработки, прогон `scripts/evaluate.py`.

Старт в Colab:
```python
!git clone <ваш репозиторий> && cd online-dekanat
!apt-get install -y tesseract-ocr tesseract-ocr-rus
!pip install -r requirements-api.txt
import sys; sys.path.insert(0, "src")
```
