#
#  Copyright (c) 2024 Jon Palmisciano. All rights reserved.
#
#  Use of this source code is governed by the BSD 3-Clause license; a full
#  copy of the license can be found in the LICENSE.txt file.
#

from binaryninja import *  # pyright: ignore

import svdparse


def apply_svd(data: BinaryView, svd: svdparse.model.System):
    logger = data.create_logger("Plugin.SVDHelper")

    rom_segment = data.get_segment_at(data.start)
    if not rom_segment:
        logger.log_error("Can't infer ROM segment, aborting...")
        return

    data.begin_undo_actions()
    data.add_user_section(
        "ROM",
        rom_segment.start,
        rom_segment.length,
        SectionSemantics.ReadOnlyCodeSectionSemantics,
    )

    for peripheral in svd.peripherals:
        if peripheral.size == 0:
            logger.log_warn(
                f'Skipping zero-length peripheral "{peripheral.name}" at {peripheral.base_address:#x}.'
            )
            continue

        data.add_user_segment(
            peripheral.base_address,
            peripheral.size,
            0,
            0,
            SegmentFlag.SegmentReadable
            | SegmentFlag.SegmentWritable
            | SegmentFlag.SegmentContainsData,  # pyright: ignore
        )
        data.add_user_section(
            peripheral.name,
            peripheral.base_address,
            peripheral.size,
            SectionSemantics.ReadWriteDataSectionSemantics,
        )

        logger.log_debug(
            f'Created peripheral section "{peripheral.name}" at {peripheral.base_address:#x}.'
        )
        for register in peripheral.registers:
            name = f"{peripheral.name}::{register.name}"
            address = peripheral.base_address + register.offset
            data.define_user_symbol(
                Symbol(SymbolType.ImportedDataSymbol, address, name)
            )
            data.define_user_data_var(
                address, "uint32_t", name
            )  # TODO: Use correct size.
            data.set_comment_at(address, register.description)
            logger.log_debug(f'Created register symbol "{name}" at {address:#x}.')

        interrupts_base = 0x40
        for interrupt in peripheral.interrupts:
            address = (
                interrupts_base + interrupt.index * 4
            )  # TODO: Remove hardcoded pointer size.

            for f in data.get_functions_containing(address):
                data.remove_function(f)

            data.define_user_data_var(address, "void*", f"{interrupt.name}_vector")
            data.set_comment_at(address, interrupt.description)

    data.commit_undo_actions()
    data.update_analysis()


def do_apply_svd(data: BinaryView):
    file_path = interaction.get_open_filename_input("SVD File")
    if not file_path:
        return

    svd = svdparse.parse_file(file_path)
    apply_svd(data, svd)


PluginCommand.register("SVD Helper\\Apply SVD File...", "", do_apply_svd)
