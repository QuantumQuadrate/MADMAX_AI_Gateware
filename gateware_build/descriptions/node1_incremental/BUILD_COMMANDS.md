# Node 1 Incremental Native Build Commands

Each command builds a native, non-entangler Kasli-SoC image from a cumulative card list.
Copy `repos/madmax-artiq-zynq/build/boot.bin` after each successful build before starting the next one.
To build and package one variant automatically, run the generator with `--build --only N`.

## 01_through_eem0_dio.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/01_through_eem0_dio.json standalone
```

## 02_through_eem1_dio.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/02_through_eem1_dio.json standalone
```

## 03_through_eem2_sampler.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/03_through_eem2_sampler.json standalone
```

## 04_through_eem3_sampler.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/04_through_eem3_sampler.json standalone
```

## 05_through_eem4_sampler.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/05_through_eem4_sampler.json standalone
```

## 06_through_eem5_zotino.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/06_through_eem5_zotino.json standalone
```

## 07_through_eem6_7_urukul.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/07_through_eem6_7_urukul.json standalone
```

## 08_through_eem8_9_urukul.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/08_through_eem8_9_urukul.json standalone
```

## 09_through_eem10_11_urukul.json

```bash
./gateware_build/scripts/build_from_json.sh gateware_build/descriptions/node1_incremental/09_through_eem10_11_urukul.json standalone
```
