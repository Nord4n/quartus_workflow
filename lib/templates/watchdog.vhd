-- watchdog.vhd — Configurable hardware watchdog timer
--
-- Counts down from TIMEOUT_CYCLES.  The system must assert kick='1' for at
-- least one clock cycle before the counter reaches zero, or expired is
-- asserted.  expired stays high until rst_n is de-asserted.
--
-- Intended use: connect expired to a system reset or an interrupt, and
-- have the firmware periodically kick the watchdog to signal it is alive.
-- Connect enable='0' to disable the WDT entirely during debugging.
--
-- Generics:
--   TIMEOUT_CYCLES : number of clock cycles before expiry (default 50_000_000
--                    = 1 second at 50 MHz, matching the DE10-Lite oscillator)
--
-- Ports:
--   clk     : system clock
--   rst_n   : synchronous reset, active low — reloads counter and clears expired
--   enable  : '1' to run the watchdog, '0' to freeze it (counter holds value)
--   kick    : one-or-more cycle pulse — reloads counter and prevents expiry
--   expired : asserted when counter reaches zero; held until reset
--
-- Waveform (TIMEOUT_CYCLES=4 for clarity):
--
--   clk     : __|‾|_|‾|_|‾|_|‾|_|‾|_|‾|_|‾|_
--   enable  : ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
--   kick    : ___|‾|_______________________
--   expired : ___________________|‾‾‾‾‾‾‾‾‾   (fires after 4 cycles without kick)
--   (counter:   3   4  3  2  1  0  0  0  0 )
--
-- Synthesis note:
--   TIMEOUT_CYCLES drives the counter width via log2_ceil.  For long timeouts
--   (e.g. 50_000_000) the counter is 26 bits — negligible resource usage.

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.math_pkg.all;

entity watchdog is
    generic (
        TIMEOUT_CYCLES : positive := 50_000_000   -- 1 s at 50 MHz
    );
    port (
        clk     : in  std_logic;
        rst_n   : in  std_logic;
        enable  : in  std_logic;
        kick    : in  std_logic;
        expired : out std_logic
    );
end entity watchdog;

architecture rtl of watchdog is

    constant CTR_W : natural := log2_ceil(TIMEOUT_CYCLES + 1);
    signal   ctr   : unsigned(CTR_W - 1 downto 0);
    signal   exp_r : std_logic;

begin

    expired <= exp_r;

    process (clk) is
    begin
        if rising_edge(clk) then
            if rst_n = '0' then
                ctr   <= to_unsigned(TIMEOUT_CYCLES, CTR_W);
                exp_r <= '0';
            elsif enable = '1' and exp_r = '0' then
                if kick = '1' then
                    ctr <= to_unsigned(TIMEOUT_CYCLES, CTR_W);
                elsif ctr = 0 then
                    exp_r <= '1';
                else
                    ctr <= ctr - 1;
                end if;
            end if;
        end if;
    end process;

end architecture rtl;
