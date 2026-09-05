# Changelog

## [2.0.0](https://github.com/jonperron/med-assist/compare/1.0.0...2.0.0) (2026-09-05)


### ⚠ BREAKING CHANGES

* **security:** drop the shared credential and warn on open deployments ([#92](https://github.com/jonperron/med-assist/issues/92))

### Features

* **security:** drop the shared credential and warn on open deployments ([#92](https://github.com/jonperron/med-assist/issues/92)) ([3072b5f](https://github.com/jonperron/med-assist/commit/3072b5fbff7ff116dffb02434b891a2f100b2c69))

## [1.0.0](https://github.com/jonperron/med-assist/compare/0.1.0...1.0.0) (2026-09-05)


### ⚠ BREAKING CHANGES

* **security:** API_ACCESS_TOKEN is required, so `docker compose up` with no .env no longer starts, and the bundled browser interface stops working in every deployment that has no authenticating proxy in front to inject the header. The page calls the API directly and provably cannot hold a secret, so the proxy documented in deploy/README.md is now how a working interface is obtained rather than an optional hardening step.

### Features

* **security:** require the credential and check the request origin ([#88](https://github.com/jonperron/med-assist/issues/88)) ([49666cd](https://github.com/jonperron/med-assist/commit/49666cdcf21b78ca8c1db249eb82ab4ca9963bbb))


### Bug Fixes

* **ci:** stop the release manifest turning the lint job red ([#83](https://github.com/jonperron/med-assist/issues/83)) ([9a63be9](https://github.com/jonperron/med-assist/commit/9a63be99d6065aa797508c119cd8e9782ccd539b))


### Documentation

* cut the root README to what a newcomer needs ([#86](https://github.com/jonperron/med-assist/issues/86)) ([2192a7f](https://github.com/jonperron/med-assist/commit/2192a7ffa8954d5a6ef6f0051ce8e50ac8c22a13))
* move the reasoning out of the READMEs into the wiki ([#89](https://github.com/jonperron/med-assist/issues/89)) ([d2f4517](https://github.com/jonperron/med-assist/commit/d2f4517c7cc1b4b718cf23f1fa773a5c973aaed0))

## 0.1.0 (2026-08-31)


### ⚠ BREAKING CHANGES

* the image no longer contains the weights. `docker run` without a mount starts a backend that answers 503 on /readyz and on both analysis routes; deployments outside docker-compose.yml must supply the mount themselves. Nothing is stored, logged or returned that was not before.
* POST /api/analyze, the result event of POST /api/analyze/stream and GET /mock_summary no longer return start or end on any entity, and the fields are gone from backend/openapi.json and the generated client types. There is no deprecation window. Nothing in frontend/ read them; a caller outside this repository that stored them loses them.
* **backend:** enforce the request ceiling and bound the containers ([#72](https://github.com/jonperron/med-assist/issues/72))
* **backend:** the four stored-document endpoints are gone, as are the UploadResponse and ExtractionResponse schemas and the retained field on AnalysisResponse. There is no deprecation window and no analyse-once, read-later flow; a document must be resubmitted to be summarised again.

### Features

* add release please workflow ([#78](https://github.com/jonperron/med-assist/issues/78)) ([04980c9](https://github.com/jonperron/med-assist/commit/04980c9a4a879086b58bac16e95eb5929fb82a41))
* add workflow docker publish ([#79](https://github.com/jonperron/med-assist/issues/79)) ([a1d10f7](https://github.com/jonperron/med-assist/commit/a1d10f7950387af9279c135295492f808056575c))
* **agent:** add agents ([#39](https://github.com/jonperron/med-assist/issues/39)) ([626c927](https://github.com/jonperron/med-assist/commit/626c927ae67dc3c5a239bd5342d200e8f28b7ebd))
* **api:** update extraction route with placeholder and 404 response ([bccba8f](https://github.com/jonperron/med-assist/commit/bccba8fe3dad5ea035f9e0cfdded0d55d9101e18))
* **api:** update extraction route with placeholder and 404 response ([#10](https://github.com/jonperron/med-assist/issues/10)) ([20fdd77](https://github.com/jonperron/med-assist/commit/20fdd770b89df865f85288198c1527d6221e82f1))
* **backend:** add dummy text extractor class with tests ([983f2dc](https://github.com/jonperron/med-assist/commit/983f2dc61ca02ce7ebde0c2e562bf10062a17962))
* **backend:** date each document and the batch it belongs to ([#67](https://github.com/jonperron/med-assist/issues/67)) ([fbcbc89](https://github.com/jonperron/med-assist/commit/fbcbc8915121cd61c39838b17a2c8096d6c5444f))
* **backend:** enforce the request ceiling and bound the containers ([#72](https://github.com/jonperron/med-assist/issues/72)) ([d35c04b](https://github.com/jonperron/med-assist/commit/d35c04bbc1c3a737a622394cf12f59a176064958))
* **backend:** improve code ([#23](https://github.com/jonperron/med-assist/issues/23)) ([4df6ec2](https://github.com/jonperron/med-assist/commit/4df6ec2e16af8d29d32cf5164c65bcb6d3c5e973))
* **backend:** remove the stored-document endpoints and drop Redis ([#71](https://github.com/jonperron/med-assist/issues/71)) ([de9522c](https://github.com/jonperron/med-assist/commit/de9522ccb137398984f780e08de8e63b1fccbff8))
* **backend:** source findings, survive unread files, pair values ([#66](https://github.com/jonperron/med-assist/issues/66)) ([1b42313](https://github.com/jonperron/med-assist/commit/1b423134075c212f4a4f23779fc7ec20b3f9358c))
* **backend:** stream analysis progress document by document ([#69](https://github.com/jonperron/med-assist/issues/69)) ([64658d1](https://github.com/jonperron/med-assist/commit/64658d11ceab69eeb6c647027e4211206c53283a))
* **ci:** set up ci ([d6e0683](https://github.com/jonperron/med-assist/commit/d6e06836e6fd0db8076a22076086fd2cc01d40be))
* **ci:** set up ci ([#9](https://github.com/jonperron/med-assist/issues/9)) ([3c82498](https://github.com/jonperron/med-assist/commit/3c824985ef4ee5b8649fbf0eccf3a19a8c655847))
* close the gap between the README and the code (phase 0) ([#56](https://github.com/jonperron/med-assist/issues/56)) ([b157a7a](https://github.com/jonperron/med-assist/commit/b157a7a0ee9be78c67429d162a50592bca4946f2))
* **dependancies:** update fastapi and uvicorn to latest version ([9e1969d](https://github.com/jonperron/med-assist/commit/9e1969d5393d9a7aea8cbf3d222edc61c2f81dc9))
* **dev:** add mock extracted_text route for dev purpose ([#20](https://github.com/jonperron/med-assist/issues/20)) ([f151b51](https://github.com/jonperron/med-assist/commit/f151b5180dd9a48760a6a5f4b6b647b00d09ec97))
* earn the footprint claim (phase 2) ([#62](https://github.com/jonperron/med-assist/issues/62)) ([03d115b](https://github.com/jonperron/med-assist/commit/03d115bbeae2d8ea31e8115ecc42b0a40395a73b))
* **endpoint:** add endpoint handling multiple upload ([#21](https://github.com/jonperron/med-assist/issues/21)) ([1456714](https://github.com/jonperron/med-assist/commit/14567146d326ce370370b5d2ad2c1fa8756c936a))
* **extractions:** add entity extractor + tests ([8b8c57c](https://github.com/jonperron/med-assist/commit/8b8c57cfdedc816a408d30e024afe0ad73d0342a))
* **extractions:** add entity extractor + tests ([#11](https://github.com/jonperron/med-assist/issues/11)) ([a68121d](https://github.com/jonperron/med-assist/commit/a68121d224e9d18167cdb63509e3d5b7f71dfcfd))
* **frontend:** add a footer with the version, the issue link and the policy ([#74](https://github.com/jonperron/med-assist/issues/74)) ([436219e](https://github.com/jonperron/med-assist/commit/436219ebfd2cc1184d6a5959a1f92a6919202894))
* **frontend:** init app ([#14](https://github.com/jonperron/med-assist/issues/14)) ([8b97409](https://github.com/jonperron/med-assist/commit/8b97409a0d55b9b51cced38de2facbbe4a1aa7f8))
* **frontend:** rebuild the interface from the design canvas ([#65](https://github.com/jonperron/med-assist/issues/65)) ([5633c34](https://github.com/jonperron/med-assist/commit/5633c346bb5f215280113dfb7b40c282a4d58e9b))
* **github:** add workflow to run tests ([c798a12](https://github.com/jonperron/med-assist/commit/c798a128c967daad51e09c5633f3a2f25d247d8a))
* **init:** init by AI ([4a648ce](https://github.com/jonperron/med-assist/commit/4a648ce223928d5ca6fb3628d408aaea652a0a6c))
* **model:** update code to use real model ([#33](https://github.com/jonperron/med-assist/issues/33)) ([cdcac69](https://github.com/jonperron/med-assist/commit/cdcac691e1053f31b3a162d42454ee7670dfe314))
* mount the model and say so when it is not loaded ([#75](https://github.com/jonperron/med-assist/issues/75)) ([cf949cf](https://github.com/jonperron/med-assist/commit/cf949cf24610aa50ddf3a8f53fbf8e35482acea9))
* **readme:** add articles references ([#24](https://github.com/jonperron/med-assist/issues/24)) ([58af5b3](https://github.com/jonperron/med-assist/commit/58af5b325ec6e3d2b26e5c79ee798e1ff7960d57))
* **readme:** update readme ([#12](https://github.com/jonperron/med-assist/issues/12)) ([9c6bb24](https://github.com/jonperron/med-assist/commit/9c6bb24e6bb9e32bfdc63cc751278a78b868c89d))
* **routes:** add response validation ([#17](https://github.com/jonperron/med-assist/issues/17)) ([748a3e4](https://github.com/jonperron/med-assist/commit/748a3e49727ec80cc7a34bd0cbd0e3ba8d8635ff))
* **security:** fix security issue on file upload ([#42](https://github.com/jonperron/med-assist/issues/42)) ([69545af](https://github.com/jonperron/med-assist/commit/69545af42f8e2afef2778d7aeeedfc5fb26755c5))
* **storage:** add in memory storage ([8e716a3](https://github.com/jonperron/med-assist/commit/8e716a3e8f6d863ab0d24d0e86922d870b8221fa))
* **storage:** add in memory storage ([#7](https://github.com/jonperron/med-assist/issues/7)) ([f32d572](https://github.com/jonperron/med-assist/commit/f32d57203b7765cde262637fba3a49eaa273546c))
* **storage:** use generated id instead of filename to save data in redis ([2e10d96](https://github.com/jonperron/med-assist/commit/2e10d96640fd8747bf40b4325c976b51b546e557))
* **storage:** use generated id instead of filename to save data in redis ([#8](https://github.com/jonperron/med-assist/issues/8)) ([7dce463](https://github.com/jonperron/med-assist/commit/7dce46358896b117ad04d7c7c0a7c63ec9d1873b))
* store less (phase 1) ([#57](https://github.com/jonperron/med-assist/issues/57)) ([847cdd1](https://github.com/jonperron/med-assist/commit/847cdd1329eb9aff84f3b8ca55e16b71097eaf7d))
* summarise documents instead of listing scored entities ([#64](https://github.com/jonperron/med-assist/issues/64)) ([35b58bd](https://github.com/jonperron/med-assist/commit/35b58bdb8e4a0404a5bad72e1b533c08be1c691e))
* **upload:** add dummy text extractor class + tests ([#3](https://github.com/jonperron/med-assist/issues/3)) ([ef8ef14](https://github.com/jonperron/med-assist/commit/ef8ef1470681255d8c68074625a80ef78e2e622b))


### Bug Fixes

* **backend:** dockerfile ([#35](https://github.com/jonperron/med-assist/issues/35)) ([69cbb3f](https://github.com/jonperron/med-assist/commit/69cbb3f0d3d271584cb546e9b4d33c698e2a1900))
* **ci:** pass tag_name to the reusable docker build workflow ([#80](https://github.com/jonperron/med-assist/issues/80)) ([b4343db](https://github.com/jonperron/med-assist/commit/b4343db4d4378666ecdeb8bb5d3866f7273ce5a2))
* close the three remaining open review items ([#73](https://github.com/jonperron/med-assist/issues/73)) ([db50120](https://github.com/jonperron/med-assist/commit/db501202012e3661acc15dbefe56fe73ade084a4))
* **extraction:** fix api and frontend component ([#16](https://github.com/jonperron/med-assist/issues/16)) ([ad3c8f2](https://github.com/jonperron/med-assist/commit/ad3c8f2336b12cd5e7220bcaa420cd141a88ebc0))
* **frontend:** display entities by categories ([#36](https://github.com/jonperron/med-assist/issues/36)) ([6380bb8](https://github.com/jonperron/med-assist/commit/6380bb830fdeb93da814ab6e823013b47b690a34))
* **model:** fix drug name being splitted in several pieces ([#37](https://github.com/jonperron/med-assist/issues/37)) ([4f270eb](https://github.com/jonperron/med-assist/commit/4f270eb0e07461535a84af6291ed5b867261bddd))
* **security:** bump libraries to latest versions ([#43](https://github.com/jonperron/med-assist/issues/43)) ([380c620](https://github.com/jonperron/med-assist/commit/380c62087f9d61e3077e44d8cc24d23bb597303d))
* **security:** fix remaining issues ([#46](https://github.com/jonperron/med-assist/issues/46)) ([6e2e2f4](https://github.com/jonperron/med-assist/commit/6e2e2f43601ed05d706df5076f1d867fe4f4b7d3))
* **upload:** fix routes in frontend application ([#15](https://github.com/jonperron/med-assist/issues/15)) ([97c9d02](https://github.com/jonperron/med-assist/commit/97c9d022c38a648e48ce86fdc413aa9aa735e7c6))


### Documentation

* **claude:** split the coding rules into path- and task-scoped files ([c5ca28e](https://github.com/jonperron/med-assist/commit/c5ca28eaa188689af0aa216215e4e558f0edbd8f))
* **claude:** stop the review and security agents quoting source ([f702c4b](https://github.com/jonperron/med-assist/commit/f702c4b9e168cfe68511b0c0dfc1ef1dcf8b7934))
* move the decision log to the local wiki ([#68](https://github.com/jonperron/med-assist/issues/68)) ([37d9ea0](https://github.com/jonperron/med-assist/commit/37d9ea0c6824db1a425f1b8459a5711bc0d9b0ea))
* point the decision log at the committed openwiki ([#70](https://github.com/jonperron/med-assist/issues/70)) ([7eb6c57](https://github.com/jonperron/med-assist/commit/7eb6c5700c32669a81a1e1b9cf0eaced5dc454ed))
