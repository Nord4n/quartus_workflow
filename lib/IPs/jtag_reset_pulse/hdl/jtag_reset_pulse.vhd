library ieee;
use ieee.std_logic_1164.all;

-- jtag_reset_pulse.vhd
--
-- Minimal reset combiner for systems with an existing top-level reset
-- synchronizer and no PLL. Intended as a drop-in replacement for
-- Reset_Combiner in Platform Designer systems where:
--
--   - The physical reset is already 2-FF synchronized at the top level
--     (no need for a second synchronizer here).
--   - There is no PLL, so PLL-lock delay is unnecessary.
--   - Programmatic CPU reset via the JTAG Avalon Master Bridge is still
--     desired (e.g. for automated firmware loading via system-console).
--
-- Ports:
--   clk           : system clock
--   i_reset_n     : physical reset, active-low (pre-synchronized by top level)
--   i_jtag_reset  : JTAG Avalon Master Bridge debug_reset_request, active-high
--   o_cpu_reset_n : CPU reset output, active-low
--
-- JTAG reset handling — edge detection:
--   i_jtag_reset is edge-detected; only rising edges generate a reset pulse
--   of PULSE_LEN clock cycles. This prevents the sustained
--   debug_reset_request assertion that occurs during close_service /
--   bridge hardware reinitialization from permanently holding the CPU in
--   reset. Each new JTAG reset request (rising edge) produces exactly one
--   bounded reset pulse, regardless of how long the signal stays high.

entity jtag_reset_pulse is
    port (
        clk           : in  std_logic;
        i_reset_n     : in  std_logic;  -- physical reset, active-low
        i_jtag_reset  : in  std_logic;  -- JTAG debug_reset_request, active-high
        o_cpu_reset_n : out std_logic   -- CPU reset output, active-low
    );
end entity jtag_reset_pulse;

architecture rtl of jtag_reset_pulse is

    -- Reset pulse length in clock cycles.
    -- 16 cycles = 320 ns @ 50 MHz — sufficient for SERV to register reset.
    constant PULSE_LEN  : integer := 16;

    signal jtag_prev    : std_logic := '0';
    signal pulse_cnt    : integer range 0 to PULSE_LEN := 0;
    signal jtag_reset_n : std_logic := '1';  -- active-low JTAG reset pulse

begin

    -- Detect rising edge of i_jtag_reset and generate a PULSE_LEN-cycle
    -- active-low reset pulse. Once the pulse expires, further assertions of
    -- i_jtag_reset (at the same level) do not extend or restart the pulse —
    -- only a new rising edge does.
    p_jtag_pulse : process(clk)
    begin
        if rising_edge(clk) then
            jtag_prev <= i_jtag_reset;
            if i_jtag_reset = '1' and jtag_prev = '0' then
                -- Rising edge: start reset pulse
                pulse_cnt    <= PULSE_LEN;
                jtag_reset_n <= '0';
            elsif pulse_cnt > 0 then
                pulse_cnt    <= pulse_cnt - 1;
                jtag_reset_n <= '0';
            else
                jtag_reset_n <= '1';
            end if;
        end if;
    end process;

    -- CPU is held in reset when the physical button is pressed
    -- OR a JTAG reset pulse is active.
    o_cpu_reset_n <= i_reset_n and jtag_reset_n;

end architecture rtl;
