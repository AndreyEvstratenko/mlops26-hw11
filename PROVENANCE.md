# Происхождение реализации

Автор отчёта: Евстратенко Андрей Дмитриевич, ИУ6-75Б.

Основа сервиса: локальное решение ДЗ 8–10 из D:/mlops26-hw8-9-10-solution. Копии исходных service.py, backends.py, release.py, README.md и CONTRACTS.txt сохранены в reference/hw8910. Модуль app/release_contracts.py является точной копией вашего release.py: сервис использует canonical, digest и verify_files при загрузке. Сохранены маршруты /health, /ready, /generate и вход prompt/max_new_tokens. max_new_tokens у CPU-имитатора задаёт число частей, а не реальных токенов; ответ явно сообщает backend_mode=simulated и output_chunks.

Обвязка Helm/мониторинга/опытов адаптирована из ранее подготовленного в этом же аккаунте проекта лабораторной 11 (valerianiv/MLOps, снимок f1cfe19b5a7ab36cd12ff0a5f2806e13874aff02). Общие файлы не выдаются за независимо разработанную реализацию. Чужие результаты, журналы и графики в эту работу не переносились. Новые результаты получены отдельно в кластере mlops-andrey11 на компьютере автора.

Изменения: собственные исходные контракты загрузки, совместимость /generate, Windows PowerShell-запуск, изолированные kubeconfig и Helm-каталоги, отдельные имя кластера и образ, данные автора, новые измерения и выводы по ним.

Кейс из лекции: Google Cloud, Vertex AI / GKE Inference Gateway. Таймкод 08:20 выбран по сообщённому автором интервалу показа слайда 08:14–08:35. Первоисточник: https://cloud.google.com/blog/products/containers-kubernetes/how-gke-inference-gateway-improved-latency-for-vertex-ai

Точный коммит исходного собственного ДЗ 8–10: e78f93b4f352921563110e59d90c789380c819a3, origin https://github.com/AndreyEvstratenko/mlops26-hw8-9-10.git.
