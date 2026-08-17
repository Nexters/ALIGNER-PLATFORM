# Changelog

## [0.3.0](https://github.com/Nexters/ALIGNER-PLATFORM/compare/aligner-platform-v0.2.1...aligner-platform-v0.3.0) (2026-08-17)


### ✨ 신규 인프라 기능 (Features)

* **gateway:** 개발 샌드박스 백엔드 도메인을 dev-api.aligneryoga.com 으로 전환 ([5dd82fc](https://github.com/Nexters/ALIGNER-PLATFORM/commit/5dd82fcbe08ac1651ede6f1ef460f23ddbe26b33))


### 🔧 설정 및 도구 (Maintenance)

* **gateway:** 구 test.aligneryoga.com 완전 정리 및 dev-api 단일화 ([226608b](https://github.com/Nexters/ALIGNER-PLATFORM/commit/226608be7754bfc01bd013e4571bd5cdc26f1edb))

## [0.2.1](https://github.com/Nexters/ALIGNER-PLATFORM/compare/aligner-platform-v0.2.0...aligner-platform-v0.2.1) (2026-08-16)


### 🐛 인프라 수정 (Fixes)

* **data:** local-path-provisioner ConfigMap을 L3(ArgoCD)에서 제거 ([d37390a](https://github.com/Nexters/ALIGNER-PLATFORM/commit/d37390a25e11690a29c8b1c4c61b2d081199bd1b))
* **gitops:** cluster.yaml PostgreSQL 이미지 버전을 실제 런타임인 16.8로 동기화 ([e257dc7](https://github.com/Nexters/ALIGNER-PLATFORM/commit/e257dc7bec3a0ea0ffd7cb0d45cc20fdddb34331))
* **gitops:** runtime-secret.keys 에서 DB_URL 제거 및 DB_PRIMARY_URL, DB_READONLY_URL 동기화 ([6c5c5e9](https://github.com/Nexters/ALIGNER-PLATFORM/commit/6c5c5e9eedb9218684b5155112a71791d69e05e8))


### 📝 런북 및 문서 (Documentation)

* README.md 시스템 아키텍처 및 3계층 플랫폼 명세 최신화 ([ad2c14b](https://github.com/Nexters/ALIGNER-PLATFORM/commit/ad2c14b34d1741d1ac8c6e6db6d29002a4506fde))
* README.md 영문 표준 기술 용어 정돈 및 라이선스 배지 제거 ([44f1d2b](https://github.com/Nexters/ALIGNER-PLATFORM/commit/44f1d2ba34a5e1cca8952c95cc1b4c07dcb7dd76))

## [0.2.0](https://github.com/Nexters/ALIGNER-PLATFORM/compare/aligner-platform-v0.1.0...aligner-platform-v0.2.0) (2026-08-16)


### ✨ 신규 인프라 기능 (Features)

* **gitops:** Argo CD App-of-Apps 활성화 및 K8s 표준 헬스체크 프로브 연동 ([#88](https://github.com/Nexters/ALIGNER-PLATFORM/issues/88)) ([e75011e](https://github.com/Nexters/ALIGNER-PLATFORM/commit/e75011ea6cafff25ddf5f997e3fd30edb8e741a9))
* **gitops:** data.yaml 및 apps.yaml (sandbox/api) 활성화하여 Argo CD 전체 워크로드 타일 연동 ([#87](https://github.com/Nexters/ALIGNER-PLATFORM/issues/87)) ([b404003](https://github.com/Nexters/ALIGNER-PLATFORM/commit/b404003ab97d2325b9ab7892535f8e0cc58322f5))


### 🐛 인프라 수정 (Fixes)

* **ci:** release-please-action 태그를 [@v4](https://github.com/v4)로 수정 ([3f0a6b3](https://github.com/Nexters/ALIGNER-PLATFORM/commit/3f0a6b3dd166360d78e1d80b7680e7891f7b7031))
* PodSecurity restricted 규격 준수를 위한 컨테이너 보안 컨텍스트 추가 ([8c51360](https://github.com/Nexters/ALIGNER-PLATFORM/commit/8c51360b7e513b1e26ad3ad575426764b119f840))


### ♻️ 구조 개선 (Refactoring)

* **repo:** 불필요한 레거시 디렉터리, .gitkeep 및 스크립트 구조 정비 ([#83](https://github.com/Nexters/ALIGNER-PLATFORM/issues/83)) ([#84](https://github.com/Nexters/ALIGNER-PLATFORM/issues/84)) ([756cda6](https://github.com/Nexters/ALIGNER-PLATFORM/commit/756cda604cfe96c12c9b3af011f6f47f6c75436c))
* 코드 스멜 제거, 보안 강화 및 가독성 레이어링 리팩토링 ([#86](https://github.com/Nexters/ALIGNER-PLATFORM/issues/86)) ([5cb7067](https://github.com/Nexters/ALIGNER-PLATFORM/commit/5cb70671684be6e3e065d0497d198269dba66a7d))

## 0.1.0 (2026-08-15)


### ✨ 신규 인프라 기능 (Features)

* **ansible:** K3s 3노드 부트스트랩과 관리 접근 안전장치 강화 ([a426ec0](https://github.com/Nexters/ALIGNER-PLATFORM/commit/a426ec01ad052ff5146e70f2046c7b0900f60f7f))
* Argo CD 고가용성 bootstrap ([#68](https://github.com/Nexters/ALIGNER-PLATFORM/issues/68)) ([a4f77ce](https://github.com/Nexters/ALIGNER-PLATFORM/commit/a4f77ce6567120fffd33de67f6af8df9ec3031bf))
* bootstrap three-node embedded-etcd k3s ([#65](https://github.com/Nexters/ALIGNER-PLATFORM/issues/65)) ([9deb073](https://github.com/Nexters/ALIGNER-PLATFORM/commit/9deb07369702a87c1b0a9c65679388a7e5976875))
* **cilium:** 연결성·복구·용량 프로덕션 Gate 추가 ([71eb2d6](https://github.com/Nexters/ALIGNER-PLATFORM/commit/71eb2d66466b95b4ae4a26bdc156b9ddbd54ac19))
* **data:** PostgreSQL·Redis·로컬 스토리지 배포 Gate 구성 ([f786e2f](https://github.com/Nexters/ALIGNER-PLATFORM/commit/f786e2f2336268d4e9b970767b9a4f10beabc944))
* **gabiactl:** 가비아 인프라를 안전하게 조회·계획하는 기반 추가 ([dbe87f1](https://github.com/Nexters/ALIGNER-PLATFORM/commit/dbe87f1c8cd7c56daf89c32a43b1a05582b7253d))
* **gitops:** Gateway·인증서·시크릿·관측 컨트롤러 구성 ([fade360](https://github.com/Nexters/ALIGNER-PLATFORM/commit/fade360b3bee2c93fab363239379c9fc2c556de3))
* **platform:** 애플리케이션 배포와 프로덕션 승인 Gate 추가 ([4b3cc76](https://github.com/Nexters/ALIGNER-PLATFORM/commit/4b3cc766d998c8cbbddfcb4b7525312d985c544b))
* Private GHCR 이미지 풀을 위한 imagePullSecrets(ghcr-secret) 연동 ([201d338](https://github.com/Nexters/ALIGNER-PLATFORM/commit/201d338be065c87fee123490ba3b8c1779993eee))
* Tailscale 전용 Argo CD HA UI 구성 ([#74](https://github.com/Nexters/ALIGNER-PLATFORM/issues/74)) ([278cf8e](https://github.com/Nexters/ALIGNER-PLATFORM/commit/278cf8e234dac27510582a424aadf4956e024fc1))
* 공인 도메인(aligneryoga.com) 진입로, Let's Encrypt 자동 SSL, PostgreSQL HA 구축 ([#76](https://github.com/Nexters/ALIGNER-PLATFORM/issues/76)) ([e4c6e3e](https://github.com/Nexters/ALIGNER-PLATFORM/commit/e4c6e3e5afb7a92dc32ff30d79454f52d3e64a55))
* 백엔드 환경변수 시크릿 계약 확정, K3s 주입 및 GitHub Actions CI/CD 연동 ([#77](https://github.com/Nexters/ALIGNER-PLATFORM/issues/77)) ([4d8c754](https://github.com/Nexters/ALIGNER-PLATFORM/commit/4d8c754c55e8ef6152cb8af3b1e17963dffe1f8b))
* 보안 컨텍스트 통일 및 서비스 어카운트 명시 ([0fda270](https://github.com/Nexters/ALIGNER-PLATFORM/commit/0fda270e5a66674c606eee8d59a08d24fdd6b8af))
* 저장소 골격과 보안 기준선 구성 ([#2](https://github.com/Nexters/ALIGNER-PLATFORM/issues/2)) ([f344004](https://github.com/Nexters/ALIGNER-PLATFORM/commit/f3440047b31dbd618aba2a1ceb155ae1088a05a2))
* 저장소 특성에 맞춘 CodeRabbit 설정 추가 ([#4](https://github.com/Nexters/ALIGNER-PLATFORM/issues/4)) ([70c951a](https://github.com/Nexters/ALIGNER-PLATFORM/commit/70c951afdb19afc1fca5ff7545a598a7a2921bf8))
* 전체 경로 HTTPRoute 라우팅 및 PostgreSQL HA 클러스터 설정 정비 ([e4a44b8](https://github.com/Nexters/ALIGNER-PLATFORM/commit/e4a44b808f422e9d63cbd5b7e014a4add7bd5d00))
* 최소 Cilium 네트워크 구성 ([#66](https://github.com/Nexters/ALIGNER-PLATFORM/issues/66)) ([0b74942](https://github.com/Nexters/ALIGNER-PLATFORM/commit/0b74942fb447346b2caea7819149d558b9d38ad0))


### 🐛 인프라 수정 (Fixes)

* ESO Application sync options 중복 제거 ([#71](https://github.com/Nexters/ALIGNER-PLATFORM/issues/71)) ([5bb75a3](https://github.com/Nexters/ALIGNER-PLATFORM/commit/5bb75a33d8e8ca801cd672a6cbe5daa334a5465f))
* ESO child app에 server-side apply 설정 ([#70](https://github.com/Nexters/ALIGNER-PLATFORM/issues/70)) ([69e6461](https://github.com/Nexters/ALIGNER-PLATFORM/commit/69e646157e6d3ce860b8678afbab55bbb2a44653))
* ESO CRD에 server-side apply 사용 ([#69](https://github.com/Nexters/ALIGNER-PLATFORM/issues/69)) ([b8abd3f](https://github.com/Nexters/ALIGNER-PLATFORM/commit/b8abd3fcb3722ea2bd1ee71d71af864eff2f530c))
* P0/P1 아키텍처 경계 강화 ([#73](https://github.com/Nexters/ALIGNER-PLATFORM/issues/73)) ([800df30](https://github.com/Nexters/ALIGNER-PLATFORM/commit/800df30508c3bfc4941c8b95e987b6da12f74a1c))
* retain minimal Hubble metrics ([#67](https://github.com/Nexters/ALIGNER-PLATFORM/issues/67)) ([0fab9c0](https://github.com/Nexters/ALIGNER-PLATFORM/commit/0fab9c02b7b71e8172dc3f7a8f07d9ac65735588))
* support bootstrap inventory for passthrough LB ([#54](https://github.com/Nexters/ALIGNER-PLATFORM/issues/54)) ([54158af](https://github.com/Nexters/ALIGNER-PLATFORM/commit/54158afde89354821d0679e59637048e3eb86f43))
* Traefik 80/443 엔트리포인트에 맞게 Gateway 리스너 80/443 정렬 ([ff5e14e](https://github.com/Nexters/ALIGNER-PLATFORM/commit/ff5e14e55a2b30dc3f18c8be9cea7e1d67ca14b2))
* Traefik entryPoints 매핑을 위해 Gateway 리스너 포트 8000/8443 연동 ([4074df1](https://github.com/Nexters/ALIGNER-PLATFORM/commit/4074df1eafaf66b877f8000a4b6fe9aac0d83fd5))
* Traefik ping probe 엔트리포인트 정정 ([#72](https://github.com/Nexters/ALIGNER-PLATFORM/issues/72)) ([3be9ef8](https://github.com/Nexters/ALIGNER-PLATFORM/commit/3be9ef805f454c8466f0488c6ee783340d10f215))
* 교차 계층 정확성 감사 — 용량 계산·방화벽·GitOps 순서·상태 관리 수정 ([#51](https://github.com/Nexters/ALIGNER-PLATFORM/issues/51)) ([03dd01e](https://github.com/Nexters/ALIGNER-PLATFORM/commit/03dd01e4c05015b8a0428ab9df5b44d19d03c385))


### ♻️ 구조 개선 (Refactoring)

* **management:** WireGuard 관리망을 Tailscale로 안전하게 전환 ([25d4d6f](https://github.com/Nexters/ALIGNER-PLATFORM/commit/25d4d6fac63d5bb4c4aa83a1a7bbc6aa06c3bdf0))


### 📝 런북 및 문서 (Documentation)

* B2 단일 버킷 백업으로 전환 ([#62](https://github.com/Nexters/ALIGNER-PLATFORM/issues/62)) ([3cc6a5e](https://github.com/Nexters/ALIGNER-PLATFORM/commit/3cc6a5eaa35c5f0a186cfb1d007b9ac0c7bb8e51))
* K3s 아키텍처 v8로 재정리 ([#5](https://github.com/Nexters/ALIGNER-PLATFORM/issues/5)) ([#6](https://github.com/Nexters/ALIGNER-PLATFORM/issues/6)) ([88c5a99](https://github.com/Nexters/ALIGNER-PLATFORM/commit/88c5a99974bd8292790054eb23b63a82ed75ee0e))
* 가비아 Gen2 API 계약 조사 문서화 ([#8](https://github.com/Nexters/ALIGNER-PLATFORM/issues/8)) ([1e47561](https://github.com/Nexters/ALIGNER-PLATFORM/commit/1e475618765c251d14e3e99117bdc1aec4f08a04))
* 운영자 Tailscale 접근 그룹 명시 ([#60](https://github.com/Nexters/ALIGNER-PLATFORM/issues/60)) ([c91f5bf](https://github.com/Nexters/ALIGNER-PLATFORM/commit/c91f5bf6ed9e5438ee14d10fc00885a4fc83ccc5))


### 🔧 설정 및 도구 (Maintenance)

* 릴리즈 초기 버전을 0.1.0으로 설정 ([347c32f](https://github.com/Nexters/ALIGNER-PLATFORM/commit/347c32f389c352e59043616ec6871e85f5f38f2c))
* 빈 postgres scaffold 제거 ([#64](https://github.com/Nexters/ALIGNER-PLATFORM/issues/64)) ([6e2da0f](https://github.com/Nexters/ALIGNER-PLATFORM/commit/6e2da0fb70729a144de0b7cece2239c2caef6fec))
* 첫 릴리즈 v0.1.0 생성을 위해 기준 버전을 0.0.0으로 조정 ([59669d8](https://github.com/Nexters/ALIGNER-PLATFORM/commit/59669d8c3b4572b05dca27179cb98ef48e9ca055))
