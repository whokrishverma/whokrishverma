name: Sync ASCII portrait

on:
  workflow_dispatch:        # manual "Run workflow" button in the Actions tab
  push:
    paths:
      - 'photo.jpg'          # runs when you swap the photo directly
      - 'make_ascii_svg.py'  # runs when you tweak the script
  schedule:
    - cron: '0 * * * *'    # also checks every hour for a changed GitHub avatar

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Determine trigger type
        id: trigger
        run: echo "event=${{ github.event_name }}" >> "$GITHUB_OUTPUT"

      - name: Download current GitHub avatar (schedule/manual runs only)
        if: steps.trigger.outputs.event != 'push'
        run: curl -sL "https://github.com/whokrishverma.png?size=460" -o photo_new.jpg

      - name: Check if avatar changed (schedule/manual runs only)
        id: check
        if: steps.trigger.outputs.event != 'push'
        run: |
          if [ -f photo.jpg ] && cmp -s photo.jpg photo_new.jpg; then
            echo "changed=false" >> "$GITHUB_OUTPUT"
          else
            echo "changed=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Adopt new avatar if changed
        if: steps.trigger.outputs.event != 'push' && steps.check.outputs.changed == 'true'
        run: mv photo_new.jpg photo.jpg

      - name: Decide whether to regenerate
        id: run_gate
        run: |
          if [ "${{ steps.trigger.outputs.event }}" = "push" ]; then
            echo "go=true" >> "$GITHUB_OUTPUT"
          elif [ "${{ steps.check.outputs.changed }}" = "true" ]; then
            echo "go=true" >> "$GITHUB_OUTPUT"
          else
            echo "go=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Cache rembg model
        if: steps.run_gate.outputs.go == 'true'
        uses: actions/cache@v4
        with:
          path: ~/.u2net
          key: u2net-model

      - name: Install dependencies
        if: steps.run_gate.outputs.go == 'true'
        run: pip install pillow numpy opencv-python-headless rembg onnxruntime

      - name: Regenerate ASCII portrait
        if: steps.run_gate.outputs.go == 'true'
        run: python make_ascii_svg_illustration_v2.py photo.jpg ascii.svg

      - name: Commit changes
        if: steps.run_gate.outputs.go == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add photo.jpg ascii.svg
          git diff --staged --quiet || git commit -m "Auto-update ASCII portrait"
          git push