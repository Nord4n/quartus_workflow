library ieee;
use ieee.std_logic_1164.all;

library vunit_lib;
context vunit_lib.vunit_context;

-- VUnit testbench for jtag_reset_pulse.vhd
--
-- Verifies edge-detection behaviour: only rising edges of i_jtag_reset
-- produce a bounded PULSE_LEN-cycle reset pulse. Sustained assertion does
-- not extend or repeat the pulse; a second rising edge re-triggers it.
--
-- Run:
--   export PATH="/mnt/c/altera_lite/25.1std/questa_fse/win64:$PATH"
--   VUNIT_SIMULATOR=modelsim python3 HW/sim/run.py
-- or with GHDL:
--   VUNIT_SIMULATOR=ghdl python3 HW/sim/run.py

entity tb_jtag_reset_pulse is
    generic (runner_cfg : string);  -- required by VUnit
end entity;

architecture tb of tb_jtag_reset_pulse is

    constant CLK_PERIOD : time    := 20 ns;   -- 50 MHz
    constant PULSE_LEN  : integer := 16;       -- must match DUT constant

    signal clk           : std_logic := '0';
    signal i_reset_n     : std_logic := '1';
    signal i_jtag_reset  : std_logic := '0';
    signal o_cpu_reset_n : std_logic;

begin

    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.jtag_reset_pulse
        port map (
            clk           => clk,
            i_reset_n     => i_reset_n,
            i_jtag_reset  => i_jtag_reset,
            o_cpu_reset_n => o_cpu_reset_n
        );

    main : process
    begin
        test_runner_setup(runner, runner_cfg);

        while test_suite loop

            -- Default: all inputs inactive, output must stay high
            i_reset_n    <= '1';
            i_jtag_reset <= '0';

            -- ----------------------------------------------------------------
            -- No resets active — output stays high
            -- ----------------------------------------------------------------
            if run("idle_no_reset") then
                wait for 5 * CLK_PERIOD;
                check_equal(o_cpu_reset_n, '1',
                    "Output must be high when no reset is asserted");

            -- ----------------------------------------------------------------
            -- Physical button reset (active-low) pulls output low
            -- ----------------------------------------------------------------
            elsif run("physical_reset") then
                wait for 2 * CLK_PERIOD;
                i_reset_n <= '0';
                wait for 2 * CLK_PERIOD;
                check_equal(o_cpu_reset_n, '0',
                    "Output must be low when physical reset is asserted");
                i_reset_n <= '1';

            -- ----------------------------------------------------------------
            -- Rising edge of i_jtag_reset starts a reset pulse
            -- ----------------------------------------------------------------
            elsif run("jtag_rising_edge_starts_pulse") then
                wait for 2 * CLK_PERIOD;
                i_jtag_reset <= '1';           -- rising edge
                wait for 2 * CLK_PERIOD;       -- 1 cycle detect + 1 cycle settle
                check_equal(o_cpu_reset_n, '0',
                    "Output must be low after rising edge of i_jtag_reset");

            -- ----------------------------------------------------------------
            -- Pulse expires after PULSE_LEN cycles; sustained high does not
            -- repeat the pulse
            -- ----------------------------------------------------------------
            elsif run("jtag_sustained_no_repeat") then
                wait for 2 * CLK_PERIOD;
                i_jtag_reset <= '1';           -- rising edge → pulse starts
                -- Wait well beyond PULSE_LEN + detection latency (add margin)
                wait for (PULSE_LEN + 5) * CLK_PERIOD;
                check_equal(o_cpu_reset_n, '1',
                    "Output must release after PULSE_LEN cycles even when i_jtag_reset stays high");

            -- ----------------------------------------------------------------
            -- A second rising edge (after falling back to '0') re-triggers
            -- the pulse
            -- ----------------------------------------------------------------
            elsif run("jtag_second_edge_retriggers") then
                -- First pulse
                wait for 2 * CLK_PERIOD;
                i_jtag_reset <= '1';
                wait for (PULSE_LEN + 5) * CLK_PERIOD;
                check_equal(o_cpu_reset_n, '1',
                    "Output must release after first pulse expires");
                -- Deassert and wait for jtag_prev to register '0'
                i_jtag_reset <= '0';
                wait for 2 * CLK_PERIOD;
                -- Second rising edge
                i_jtag_reset <= '1';
                wait for 2 * CLK_PERIOD;
                check_equal(o_cpu_reset_n, '0',
                    "Second rising edge must re-trigger the reset pulse");

            end if;

        end loop;

        test_runner_cleanup(runner);
    end process;

end architecture;
