#!/usr/bin/env python3
"""Validate an arm64e Mach-O embedded code-signature structure."""

from __future__ import annotations

import hashlib
import hmac
import struct
import sys
from pathlib import Path


MH_MAGIC_64 = 0xFEEDFACF
FAT_MAGIC = 0xCAFEBABE
FAT_MAGIC_64 = 0xCAFEBABF
CPU_TYPE_ARM64 = 0x0100000C
CPU_SUBTYPE_ARM64E = 2
MH_DYLIB = 6
LC_CODE_SIGNATURE = 0x1D
CSMAGIC_EMBEDDED_SIGNATURE = 0xFADE0CC0
CSMAGIC_CODEDIRECTORY = 0xFADE0C02
CSSLOT_CODEDIRECTORY = 0
CSSLOT_ALTERNATE_CODEDIRECTORIES = 0x1000
CSSLOT_ALTERNATE_CODEDIRECTORY_LIMIT = 0x1005
CODEDIRECTORY_EARLIEST_VERSION = 0x20001
CODEDIRECTORY_SUPPORTS_CODE_LIMIT_64 = 0x20300
CODEDIRECTORY_LATEST_SUPPORTED_VERSION = 0x20600

HASH_ALGORITHMS = {
    1: ("sha1", 20),
    2: ("sha256", 32),
    3: ("sha256", 20),
    4: ("sha384", 48),
    5: ("sha512", 64),
}


class VerificationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def is_arm64e(cpu_type: int, cpu_subtype: int) -> bool:
    return cpu_type == CPU_TYPE_ARM64 and (cpu_subtype & 0x00FFFFFF) == CPU_SUBTYPE_ARM64E


def select_arm64e_slice(data: bytes) -> bytes:
    require(len(data) >= 4, "file is too short")
    magic_be = struct.unpack_from(">I", data, 0)[0]
    if magic_be not in (FAT_MAGIC, FAT_MAGIC_64):
        return data

    require(len(data) >= 8, "fat header is truncated")
    arch_count = struct.unpack_from(">I", data, 4)[0]
    require(0 < arch_count <= 64, "fat architecture count is invalid")
    entry_size = 20 if magic_be == FAT_MAGIC else 32
    table_end = 8 + arch_count * entry_size
    require(table_end <= len(data), "fat architecture table is truncated")

    for index in range(arch_count):
        offset = 8 + index * entry_size
        if magic_be == FAT_MAGIC:
            cpu_type, cpu_subtype, slice_offset, slice_size, _align = struct.unpack_from(
                ">IIIII", data, offset
            )
        else:
            cpu_type, cpu_subtype, slice_offset, slice_size, _align, _reserved = struct.unpack_from(
                ">IIQQII", data, offset
            )
        if not is_arm64e(cpu_type, cpu_subtype):
            continue
        require(slice_size > 0, "arm64e slice is empty")
        require(slice_offset >= table_end, "arm64e slice overlaps fat header")
        require(slice_offset + slice_size <= len(data), "arm64e slice exceeds file bounds")
        return data[slice_offset : slice_offset + slice_size]

    raise VerificationError("fat Mach-O has no arm64e slice")


def locate_code_signature(macho: bytes) -> tuple[int, int]:
    require(len(macho) >= 32, "Mach-O header is truncated")
    magic, cpu_type, cpu_subtype, file_type, command_count, command_bytes, _flags, _reserved = (
        struct.unpack_from("<IiiIIIII", macho, 0)
    )
    require(magic == MH_MAGIC_64, "slice is not a little-endian 64-bit Mach-O")
    require(is_arm64e(cpu_type, cpu_subtype), "slice is not arm64e")
    require(file_type == MH_DYLIB, "Mach-O is not a dynamic library")
    require(0 < command_count <= 4096, "load-command count is invalid")
    commands_end = 32 + command_bytes
    require(commands_end <= len(macho), "load-command region exceeds slice bounds")

    cursor = 32
    signature: tuple[int, int] | None = None
    for _ in range(command_count):
        require(cursor + 8 <= commands_end, "load command header is truncated")
        command, command_size = struct.unpack_from("<II", macho, cursor)
        require(command_size >= 8 and command_size % 8 == 0, "load command size is invalid")
        require(cursor + command_size <= commands_end, "load command exceeds declared region")
        if command == LC_CODE_SIGNATURE:
            require(signature is None, "multiple LC_CODE_SIGNATURE commands found")
            require(command_size >= 16, "LC_CODE_SIGNATURE is truncated")
            data_offset, data_size = struct.unpack_from("<II", macho, cursor + 8)
            signature = (data_offset, data_size)
        cursor += command_size

    require(cursor == commands_end, "load-command sizes do not match sizeofcmds")
    if signature is None:
        raise VerificationError("LC_CODE_SIGNATURE is missing")
    require(signature[0] >= commands_end, "code-signature payload overlaps load commands")
    return signature


def read_c_string(blob: bytes, offset: int, minimum_offset: int, label: str) -> int:
    require(minimum_offset <= offset < len(blob), f"{label} offset is out of bounds")
    terminator = blob.find(b"\0", offset)
    require(terminator >= offset, f"{label} is not NUL terminated")
    require(terminator > offset, f"{label} is empty")
    return terminator + 1


def validate_code_directory(code_directory: bytes, macho: bytes, signature_offset: int) -> None:
    require(len(code_directory) >= 44, "CodeDirectory base header is truncated")
    (
        magic,
        declared_length,
        version,
        _flags,
        hash_offset,
        identifier_offset,
        special_slots,
        code_slots,
        code_limit_32,
        hash_size,
        hash_type,
        _platform,
        page_size_log2,
        _spare2,
    ) = struct.unpack_from(">9I4BI", code_directory, 0)
    require(magic == CSMAGIC_CODEDIRECTORY, "nested blob is not a CodeDirectory")
    require(declared_length == len(code_directory), "CodeDirectory length is inconsistent")
    require(
        CODEDIRECTORY_EARLIEST_VERSION
        <= version
        <= CODEDIRECTORY_LATEST_SUPPORTED_VERSION,
        f"unsupported CodeDirectory version 0x{version:x}",
    )

    minimum_header = 44
    scatter_offset = 0
    team_offset = 0
    code_limit_64 = 0
    code_limit = code_limit_32
    if version >= 0x20100:
        minimum_header = 48
        require(len(code_directory) >= minimum_header, "CodeDirectory scatter header is truncated")
        scatter_offset = struct.unpack_from(">I", code_directory, 44)[0]
    if version >= 0x20200:
        minimum_header = 52
        require(len(code_directory) >= minimum_header, "CodeDirectory team header is truncated")
        team_offset = struct.unpack_from(">I", code_directory, 48)[0]
    if version >= CODEDIRECTORY_SUPPORTS_CODE_LIMIT_64:
        minimum_header = 64
        require(len(code_directory) >= minimum_header, "CodeDirectory 64-bit limit header is truncated")
        code_limit_64 = struct.unpack_from(">Q", code_directory, 56)[0]
        if code_limit_64 != 0:
            require(
                code_limit_32 == 0,
                "CodeDirectory has conflicting 32-bit and 64-bit code limits",
            )
            code_limit = code_limit_64
    if version >= 0x20400:
        minimum_header = 88
        require(len(code_directory) >= minimum_header, "CodeDirectory exec-segment header is truncated")
    if version >= 0x20500:
        minimum_header = 96
        require(len(code_directory) >= minimum_header, "CodeDirectory runtime header is truncated")
    if version >= 0x20600:
        minimum_header = 108
        require(len(code_directory) >= minimum_header, "CodeDirectory linkage header is truncated")

    require(scatter_offset == 0, "scatter CodeDirectories are unsupported")
    identifier_end = read_c_string(code_directory, identifier_offset, minimum_header, "identifier")
    metadata_end = identifier_end
    if team_offset != 0:
        metadata_end = max(
            metadata_end,
            read_c_string(code_directory, team_offset, minimum_header, "team identifier"),
        )

    algorithm = HASH_ALGORITHMS.get(hash_type)
    require(algorithm is not None, f"unsupported CodeDirectory hash type {hash_type}")
    assert algorithm is not None
    algorithm_name, expected_hash_size = algorithm
    require(hash_size == expected_hash_size, "CodeDirectory hash size does not match hash type")
    require(12 <= page_size_log2 <= 20, "CodeDirectory page-size exponent is invalid")
    page_size = 1 << page_size_log2
    require(code_limit == signature_offset, "CodeDirectory does not cover all bytes before signature")
    expected_code_slots = (code_limit + page_size - 1) // page_size
    require(code_slots == expected_code_slots, "CodeDirectory code-slot count is inconsistent")
    require(code_slots > 0, "CodeDirectory has no code slots")

    special_hash_bytes = special_slots * hash_size
    require(hash_offset >= special_hash_bytes, "CodeDirectory special-slot table underflows")
    special_hash_start = hash_offset - special_hash_bytes
    require(special_hash_start >= metadata_end, "CodeDirectory hashes overlap metadata")
    code_hash_end = hash_offset + code_slots * hash_size
    require(code_hash_end <= len(code_directory), "CodeDirectory code hashes exceed blob bounds")

    for slot in range(code_slots):
        page_start = slot * page_size
        page_end = min(page_start + page_size, code_limit)
        digest = hashlib.new(algorithm_name, macho[page_start:page_end]).digest()[:hash_size]
        stored_start = hash_offset + slot * hash_size
        stored = code_directory[stored_start : stored_start + hash_size]
        require(hmac.compare_digest(digest, stored), f"CodeDirectory code-slot hash {slot} mismatches")


def validate_superblob(macho: bytes, data_offset: int, data_size: int) -> int:
    require(data_size >= 12, "code-signature payload is too short")
    require(data_offset >= 32, "code-signature offset overlaps Mach-O header")
    require(data_offset + data_size <= len(macho), "code-signature payload exceeds slice bounds")
    require(
        data_offset + data_size == len(macho),
        "code-signature payload is not final in slice",
    )

    signature = macho[data_offset : data_offset + data_size]
    magic, total_length, blob_count = struct.unpack_from(">III", signature, 0)
    require(magic == CSMAGIC_EMBEDDED_SIGNATURE, "embedded signature is not a SuperBlob")
    require(12 <= total_length <= data_size, "SuperBlob length is out of bounds")
    require(blob_count <= 1024, "SuperBlob index count is unreasonable")
    index_end = 12 + blob_count * 8
    require(index_end <= total_length, "SuperBlob index table is truncated")

    code_directories = 0
    primary_code_directories = 0
    seen_slot_types: set[int] = set()
    nested_ranges: list[tuple[int, int]] = []
    for index in range(blob_count):
        slot_type, blob_offset = struct.unpack_from(">II", signature, 12 + index * 8)
        require(slot_type not in seen_slot_types, f"duplicate SuperBlob slot 0x{slot_type:x}")
        seen_slot_types.add(slot_type)
        require(blob_offset >= index_end, "nested blob overlaps SuperBlob index table")
        require(blob_offset + 8 <= total_length, "nested blob header is out of bounds")
        blob_magic, blob_length = struct.unpack_from(">II", signature, blob_offset)
        require(blob_length >= 8, "nested blob length is invalid")
        require(blob_offset + blob_length <= total_length, "nested blob exceeds SuperBlob bounds")
        nested_ranges.append((blob_offset, blob_offset + blob_length))
        code_directory_slot = slot_type == CSSLOT_CODEDIRECTORY or (
            CSSLOT_ALTERNATE_CODEDIRECTORIES
            <= slot_type
            < CSSLOT_ALTERNATE_CODEDIRECTORY_LIMIT
        )
        if blob_magic == CSMAGIC_CODEDIRECTORY:
            require(code_directory_slot, f"CodeDirectory uses invalid slot 0x{slot_type:x}")
            validate_code_directory(
                signature[blob_offset : blob_offset + blob_length], macho, data_offset
            )
            code_directories += 1
            if slot_type == CSSLOT_CODEDIRECTORY:
                primary_code_directories += 1
        else:
            require(not code_directory_slot, f"slot 0x{slot_type:x} is not a CodeDirectory")

    nested_ranges.sort()
    for previous, current in zip(nested_ranges, nested_ranges[1:]):
        require(previous[1] <= current[0], "nested SuperBlob entries overlap")

    require(primary_code_directories == 1, "SuperBlob must have exactly one primary CodeDirectory")
    return code_directories


def verify(path: Path) -> None:
    raw = path.read_bytes()
    macho = select_arm64e_slice(raw)
    data_offset, data_size = locate_code_signature(macho)
    code_directories = validate_superblob(macho, data_offset, data_size)
    print(
        f"MACHO_SIGNATURE_OK path={path} arm64e=true "
        f"code_signature_offset={data_offset} code_signature_size={data_size} "
        f"code_directories={code_directories}"
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <Mach-O>", file=sys.stderr)
        return 2
    try:
        verify(Path(sys.argv[1]))
    except (OSError, struct.error, VerificationError) as error:
        print(f"MACHO_SIGNATURE_INVALID: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
