[working-directory: 'demos']
deploy:
    #! /usr/bin/env bash
    # Get all the folders in demos
    for dir in */; do
      pushd "$dir" > /dev/null

      # Skip if no prefect.yaml here
      if [[ ! -f "prefect.yaml" ]]; then
        echo "Skipping '$(pwd)'; no prefect.yaml found."
        popd > /dev/null
        continue
      fi

      echo "Deploying '$(pwd)' with prefect.yaml"
      uv run "{{justfile_directory()}}/scripts/shim.py" prefect deploy --all

      popd > /dev/null
    done
