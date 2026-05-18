# CLI Reference

## Inspect preset

```bash
photo-restorer inspect-config --preset family_photo_default
```

## Detect photos only

```bash
photo-restorer detect ./scans --out ./projects/demo/project.json
```

## Crop-only batch

```bash
photo-restorer run ./scans --preset crop_only --out ./outputs/crops --only-crop --save-intermediate
```

## Default family restoration pipeline

```bash
photo-restorer run ./scans --preset family_photo_default --out ./outputs/family --save-intermediate
```

Current model adapters are placeholders except crop/orientation. The command contract is stable so real adapters can replace them without changing CLI/UI usage.
