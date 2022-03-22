# CI workflow

## Debugging

The CI/CD process can be hard to debug because it's not simple to run parts of it locally. The app is built into
docker images and run in a complete environment (backend, web, data pipelines, postgres, elasticsearch, mail) that
doesn't match what we usually run locally for development, nor the deployed cloud environment.

### Cloud debugging (in-situ)

GitHub connects to our self-hosted GitHub Actions task runner instance to actually execute on our workflows. It is
located in the `civic-eagle-enview-dev` project in Google Cloud as a Compute Engine VM Instance called
[github-runner-1](https://console.cloud.google.com/compute/instancesDetail/zones/us-central1-a/instances/github-runner-1?project=civic-eagle-enview-dev).
You can find the connection to this runner in [GitHub project config](https://github.com/civic-eagle/enview/settings/actions/runners).

You can log into this runner VM by going through the GCP Console or using gcloud CLI to connect as an SSH session.
Once in there, you can watch `docker ps` to see docker containers being run (and try to catch log output) and things like
`df -h` to see if the VM is running out of disk space.

### Local debugging

But to have better operational control to really dig into part of the workflow, you want to run individual steps
locally. General tips:

* Look at the actual commands being run in a GitHub action run. Just looking at the ci.yaml config obscures a lot,
  because it uses predefined Actions to accomplish repetitive/detailed tasks.
* To build the docker images, you need docker buildx installed, which only comes with later versions of docker
* Do a new, fresh checkout of the `enview` code repo (to a new folder) rather than trying to run this stuff within
  your existing checkout. Docker stuff will build faster (smaller file context) and fewer variables
* Make sure you checkout the same commit locally as the one you are comparing from a GH Actions run

#### Running Browser Tests

Browser test have historically been somewhat flaky within the CI/CD environment. Here are steps I followed to run them
in the way that this CI workflow does. Please note that these steps may change as `ci.yaml` is changed! See tip above
about double checking comparison between command you run locally and what is run in GH Actions output.

* Checkout the commit and note the commit SHA. In my case `b9e3bbc5a05173622ae51050e11757e72558c299`. This is used throughout.
* Build the `tester` image: `docker buildx build --target tester -t enview/tester:b9e3bbc5a05173622ae51050e11757e72558c299 .`
* Build the `builder` image: `docker buildx build --tag enview/builder:b9e3bbc5a05173622ae51050e11757e72558c299 --target builder --load .`
* Build the `pipeline` image: `docker buildx build --tag enview/pipeline:b9e3bbc5a05173622ae51050e11757e72558c299 --load ./data/pipeline`
* Bring up the environment: `TAG=b9e3bbc5a05173622ae51050e11757e72558c299 docker-compose --project-name browser-test_b9e3bbc5_a778bf3e-706b-4f23-bd18-5ebf51896fba up -d`
* Run the data seed step:

```shell
 docker run --rm -i \
--network browser-test_b9e3bbc5_a778bf3e-706b-4f23-bd18-5ebf51896fba_default \
-e NODE_ENV=test \
-e CE_BE_HOST=backend.enview \
-e DATABASE_HOST=db_test \
-e DATABASE_PORT=5432 \
enview/tester:b9e3bbc5a05173622ae51050e11757e72558c299 \
yarn workspace @enview/backend knex seed:run
```

* Run the pipeline data ingestion step:

```shell
  docker run --rm -i \
  --network browser-test_b9e3bbc5_a778bf3e-706b-4f23-bd18-5ebf51896fba_default \
  -e ENV_FOR_DYNACONF=test \
  -e CE_ENVIEW_API_HOST=http://backend.enview.com \
  enview/pipeline:b9e3bbc5a05173622ae51050e11757e72558c299 \
  poetry run poe load-test-data
```

* Run browser tests

```shell
docker run --rm -i \
  --network browser-test_b9e3bbc5_a778bf3e-706b-4f23-bd18-5ebf51896fba_default \
  -e CE_BROWSER_TESTS_SHOULD_RUN_IN_DOCKER=1 \
  -e CE_MAILDEV_HOST=maildev \
  -e CE_WEB_URL=http://enview.com \
  -e REACT_APP_API_URL=http://backend.enview.com \
  enview/tester:b9e3bbc5a05173622ae51050e11757e72558c299 \
  yarn workspace web browser-tests
```

You can iterate on modifications to frontend code and re-running browser tests. The above command runs a disposable container,
while meanwhile the supporting `docker-compose` environemnt is still running. Simply do this loop:

* modify frontend code
* re-build the `tester` image
* re-run browser tests

(if you need to modify backend code, then you will need to cleanup and bring the whole thing up again, because backend
is part of the `docker-compose` environment)

One more note: if you want to mount a directory from your computer to output, for example, screenshots from the
headless browser, add the `--mount` argument, for example where I mount my host computer's `/tmp/btss` folder: 

```shell
docker run --rm -i \
  --network browser-test_b9e3bbc5_a778bf3e-706b-4f23-bd18-5ebf51896fba_default \
  -e CE_BROWSER_TESTS_SHOULD_RUN_IN_DOCKER=1 \
  -e CE_MAILDEV_HOST=maildev \
  -e CE_WEB_URL=http://enview.com \
  -e REACT_APP_API_URL=http://backend.enview.com \
  --mount type=bind,source=/tmp/btss,target=/tmp/btss \
  enview/tester:b9e3bbc5a05173622ae51050e11757e72558c299 \
  yarn workspace web browser-tests
```

* Finally, clean up the `docker-compose` environment: `TAG=b9e3bbc5a05173622ae51050e11757e72558c299 docker-compose --project-name browser-test_b9e3bbc5_a778bf3e-706b-4f23-bd18-5ebf51896fba down`
