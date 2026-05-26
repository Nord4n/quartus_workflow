-- sync_pkg.vhd — Synchronization utilities for CDC and metastability prevention
--
-- Provides reusable procedures for clock domain crossing (CDC) and
-- metastability prevention.
--
-- Usage:
--   library ieee;
--   use ieee.std_logic_1164.all;
--   use work.sync_pkg.all;
--
--   -- Declare intermediate signals in calling architecture:
--   signal rst_meta   : std_logic;
--   signal rst_sync_n : std_logic;
--
--   -- In a clocked/async process:
--   sync_reset(clk, async_rst_n, rst_meta, rst_sync_n);
--
-- Note on sync_vector (multi-bit CDC):
--   A naive N-wide 2-FF synchronizer is only safe when the vector is
--   Gray-coded or quasi-static (changes much slower than both clocks).
--   No generic sync_vector procedure is provided here to avoid misuse.
--   Use a proper handshake, FIFO, or Gray-coded counter at the CDC boundary.

library ieee;
use ieee.std_logic_1164.all;

package sync_pkg is

    -- sync_bit: 2-FF synchronizer for a single-bit asynchronous input.
    --
    -- Prevents metastability by passing the asynchronous input through two
    -- flip-flops clocked by the destination clock domain.  The caller must
    -- declare `stage1` as a signal in their architecture — this ensures the
    -- intermediate register is synthesized as a real flip-flop rather than
    -- being optimized away.
    --
    -- Parameters:
    --   clk    : destination clock
    --   rst_n  : synchronous reset, active low (consistent with DE10-Lite KEY)
    --   async  : asynchronous input to synchronize
    --   stage1 : first FF stage — declare as signal in calling architecture
    --   sync   : synchronized output (two clock cycles of latency)
    procedure sync_bit (
        signal clk    : in    std_logic;
        signal rst_n  : in    std_logic;
        signal async  : in    std_logic;
        signal stage1 : inout std_logic;
        signal sync   : out   std_logic
    );

    -- sync_reset: Asynchronous assert, synchronous de-assert reset synchronizer.
    --
    -- The recommended reset strategy for FPGA designs.  The reset propagates
    -- immediately when async_rst_n goes low (no clock required — safe for
    -- powering up or glitch-induced resets).  De-assertion is held until two
    -- consecutive rising edges of clk, preventing metastability on release.
    --
    -- Both internal FFs are preset to '0' on async reset assertion; on
    -- de-assertion they shift '1' toward rst_sync_n over two cycles.
    --
    -- Parameters:
    --   clk        : destination clock domain
    --   async_rst_n: asynchronous reset input, active low
    --   stage1     : first FF stage — declare as signal in calling architecture
    --   rst_sync_n : synchronized reset output, active low
    procedure sync_reset (
        signal clk         : in    std_logic;
        signal async_rst_n : in    std_logic;
        signal stage1      : inout std_logic;
        signal rst_sync_n  : out   std_logic
    );

    -- sync_pulse: Single-pulse clock domain crossing via toggle handshake.
    --
    -- Safely transfers a single-cycle pulse from src_clk to dst_clk without
    -- data loss.  The source pulse toggles a register; the toggle is captured
    -- by a 2-FF synchronizer in the destination domain; an XOR edge detector
    -- recreates a one-cycle pulse in dst_clk.
    --
    -- Constraint: the source pulse must be at least one src_clk cycle wide and
    -- must not fire again until the toggle has propagated (two dst_clk cycles
    -- minimum).  For back-to-back pulses at high rates, use a FIFO instead.
    --
    -- Parameters:
    --   src_clk  : source clock domain
    --   src_pulse: single-cycle pulse in source domain
    --   dst_clk  : destination clock domain
    --   toggle   : toggle FF — declare as signal in calling architecture
    --   stage1   : sync FF 1 — declare as signal in calling architecture
    --   stage2   : sync FF 2 — declare as signal in calling architecture
    --   dst_pulse: re-created single-cycle pulse in destination domain
    procedure sync_pulse (
        signal src_clk  : in    std_logic;
        signal src_pulse : in    std_logic;
        signal dst_clk  : in    std_logic;
        signal toggle   : inout std_logic;
        signal stage1   : inout std_logic;
        signal stage2   : inout std_logic;
        signal dst_pulse : out   std_logic
    );

end package sync_pkg;


package body sync_pkg is

    procedure sync_bit (
        signal clk    : in    std_logic;
        signal rst_n  : in    std_logic;
        signal async  : in    std_logic;
        signal stage1 : inout std_logic;
        signal sync   : out   std_logic
    ) is
    begin
        if rst_n = '0' then
            stage1 <= '0';
            sync   <= '0';
        elsif rising_edge(clk) then
            stage1 <= async;
            sync   <= stage1;
        end if;
    end procedure sync_bit;


    procedure sync_reset (
        signal clk         : in    std_logic;
        signal async_rst_n : in    std_logic;
        signal stage1      : inout std_logic;
        signal rst_sync_n  : out   std_logic
    ) is
    begin
        if async_rst_n = '0' then
            stage1    <= '0';
            rst_sync_n <= '0';
        elsif rising_edge(clk) then
            stage1    <= '1';
            rst_sync_n <= stage1;
        end if;
    end procedure sync_reset;


    procedure sync_pulse (
        signal src_clk   : in    std_logic;
        signal src_pulse : in    std_logic;
        signal dst_clk   : in    std_logic;
        signal toggle    : inout std_logic;
        signal stage1    : inout std_logic;
        signal stage2    : inout std_logic;
        signal dst_pulse : out   std_logic
    ) is
    begin
        -- Source domain: convert pulse to toggle
        if rising_edge(src_clk) then
            if src_pulse = '1' then
                toggle <= not toggle;
            end if;
        end if;

        -- Destination domain: 2-FF synchronizer + XOR edge detector
        if rising_edge(dst_clk) then
            stage1   <= toggle;
            stage2   <= stage1;
            dst_pulse <= stage1 xor stage2;
        end if;
    end procedure sync_pulse;

end package body sync_pkg;
