#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
LiteX standalone SoC generator.

This generator reduces the scope of LiteX to CPU/Peripherals selection/integration and to the creation
of SoC with MMAP/Streaming DMA interfaces that can be reintegrated in external designs (or LiteX SoC).
Think of it as a mini Nios SOPC Builder/ Zynq or Microblaze Subsystem generator that offers you the
possibility to reuse any of CPU supported by LiteX :)
"""

import argparse

from migen import *

from litex.build.generic_platform import *

from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi

# IOs/Interfaces -----------------------------------------------------------------------------------

def get_common_ios():
    return [
        # Clk/Rst.
        ("clk", 0, Pins(1)),
        ("rst", 0, Pins(1)),
    ]

def get_uart_ios():
    return [
        # Serial
        ("uart", 0,
            Subsignal("tx",  Pins(1)),
            Subsignal("rx", Pins(1)),
        )
    ]

def get_debug_ios(debug_width=8):
    return [
        ("debug", 0, Pins(debug_width)),
    ]

# Platform -----------------------------------------------------------------------------------------

class Platform(GenericPlatform):
    def build(self, fragment, build_dir, build_name, **kwargs):
        print('build_dir : ', build_dir)
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)
        conv_output = self.get_verilog(fragment, name=build_name)
        conv_output.write(f"{build_name}.v")

# LiteX SoC Generator ------------------------------------------------------------------------------

class LiteXSoCGenerator(SoCMini):
    #def __init__(self, name="litex_soc", sys_clk_freq=int(50e6), **kwargs):
    def __init__(self, n_master_i, n_slave_i, name="litex_soc", sys_clk_freq=int(50e6), **kwargs):
        # Platform ---------------------------------------------------------------------------------
        print("#"*20, 'start platform')
        platform = Platform(device="", io=get_common_ios())
        print("#"*20, 'END platform')
        platform.name = name
        platform.add_extension(get_uart_ios())
        self.kwargs = kwargs #added by naouel
        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(
            clk = platform.request("clk"),
            rst = platform.request("rst"),
        )

        # SoC --------------------------------------------------------------------------------------
        #if kwargs["uart_name"] == "serial":
            #kwargs["uart_name"] = "uart"
        if self.kwargs["uart_name"] == "serial":
            self.kwargs["uart_name"] = "uart"
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, ident=f"LiteX standalone SoC - {name}", **kwargs)
#####changed part#######################################################################################
        # MMAP Master Interface --------------------------------------------------------------------
        # FIXME: Allow Region configuration.
        print("#"*20, 'befor index n_master_i')
        for n in range(n_master_i):
            print("#"*20, 'index n_master_i', n)
            origins = [0xa000_0000, 0xb000_0000, 0xc000_0000, 0xd000_0000]
            self.add_master_interface(mmap_id=n, origin=origins[n])

        # MMAP Slave Interface ---------------------------------------------------------------------
        s_bus = {
            "wishbone": wishbone.Interface(),
            "axi-lite": axi.AXILiteInterface(),

        }[self.kwargs["bus_standard"]]
        for i in range(n_slave_i):
            i_name = f"mmap_s_{i}"
            self.bus.add_master(name=i_name, master=s_bus)
            platform.add_extension(s_bus.get_ios(i_name))
            wb_pads = platform.request(i_name)
            self.comb += s_bus.connect_to_pads(wb_pads, mode="slave")

        # Debug ------------------------------------------------------------------------------------
        platform.add_extension(get_debug_ios())
        debug_pads = platform.request("debug")
        self.comb += [
            # Export Signal(s) for debug.
            debug_pads[0].eq(0),  # 0.
            debug_pads[1].eq(1),  # 1.
            # Etc...
        ]
        # self.add_timer()

    def add_master_interface(self, mmap_id, origin=0xa0000000):
        assert isinstance(mmap_id, int)
        # MMAP Master Interface --------------------------------------------------------------------
        m_bus = {
            "wishbone": wishbone.Interface(),
            "axi-lite": axi.AXILiteInterface(),
        }[self.kwargs["bus_standard"]]
        wb_region = SoCRegion(origin=origin, size=0x10000000, cached=False)
        self.bus.add_slave(name="mmap_m_{}".format(mmap_id), slave=m_bus, region=wb_region)
        self.platform.add_extension(m_bus.get_ios("mmap_m_{}".format(mmap_id)))
        wb_pads = self.platform.request("mmap_m_{}".format(mmap_id))
        self.comb += m_bus.connect_to_pads(wb_pads, mode="master")
#####fin changed part#######################################################################################
# Build --------------------------------------------------------------------------------------------
def main():
    # Arguments.
    from litex.soc.integration.soc import LiteXSoCArgumentParser
    parser = LiteXSoCArgumentParser(description="LiteX standalone SoC generator")
    target_group = parser.add_argument_group(title="Generator options")
    target_group.add_argument("--name",          default="litex_soc", help="SoC Name.")
    target_group.add_argument("--n_master_i", default=int(2), help="Number of master interfaces.")
    target_group.add_argument("--n_slave_i", default=int(0), help="Number of slave interfaces.")
    target_group.add_argument("--build",         action="store_true", help="Build SoC.")
    target_group.add_argument("--sys-clk-freq",  default=int(50e6),   help="System clock frequency.")
    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()

    # SoC.
    soc = LiteXSoCGenerator(
        name         = args.name,
        sys_clk_freq = int(float(args.sys_clk_freq)),
        n_master_i=int(args.n_master_i),
        n_slave_i=int(args.n_slave_i),
        **soc_core_argdict(args)
    )

    # Build.
    builder = Builder(soc, **builder_argdict(args))
    builder.build(build_name=args.name, run=args.build)

if __name__ == "__main__":
    main()
