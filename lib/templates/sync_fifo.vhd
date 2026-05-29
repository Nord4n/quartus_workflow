-- sync_fifo.vhd — Synchronous FIFO with configurable depth and width
--
-- Single-clock FIFO using a circular buffer.  Read and write ports operate
-- in the same clock domain.  Uses math_pkg.log2_ceil to derive the address
-- width from the DEPTH generic, so DEPTH must be a power of two.
--
-- Generics:
--   DATA_W : data bus width in bits (default 8)
--   DEPTH  : number of entries; must be a power of two (default 16)
--
-- Ports:
--   clk    : system clock
--   rst_n  : synchronous reset, active low — clears pointers and flags
--   wr_en  : write enable (ignored when full)
--   wr_data: data to write
--   rd_en  : read enable (ignored when empty)
--   rd_data: data read (valid on the cycle after rd_en when not empty)
--   full   : asserted when no write slots remain
--   empty  : asserted when no read data is available
--   count  : number of entries currently stored
--
-- Waveform (DEPTH=4, DATA_W=8):
--
--   clk     : __|‾|_|‾|_|‾|_|‾|_|‾|_
--   wr_en   : ___|‾‾‾‾‾‾‾|___________
--   wr_data : ---< A >< B >----------
--   full    : _____________________|‾‾  (asserts when count == DEPTH)
--   rd_en   : _____________|‾‾‾‾‾|___
--   rd_data : -------------< A >< B >
--   empty   : ‾‾‾|_________|‾‾‾‾‾‾‾‾  (clears after first write)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.math_pkg.all;

entity sync_fifo is
    generic (
        DATA_W : positive := 8;
        DEPTH  : positive := 16
    );
    port (
        clk     : in  std_logic;
        rst_n   : in  std_logic;

        wr_en   : in  std_logic;
        wr_data : in  std_logic_vector(DATA_W - 1 downto 0);

        rd_en   : in  std_logic;
        rd_data : out std_logic_vector(DATA_W - 1 downto 0);

        full    : out std_logic;
        empty   : out std_logic;
        count   : out std_logic_vector(log2_ceil(DEPTH) downto 0)
    );
end entity sync_fifo;

architecture rtl of sync_fifo is

    constant ADDR_W : natural := log2_ceil(DEPTH);

    type mem_t is array (0 to DEPTH - 1) of std_logic_vector(DATA_W - 1 downto 0);
    signal mem : mem_t;

    signal wr_ptr  : unsigned(ADDR_W - 1 downto 0);
    signal rd_ptr  : unsigned(ADDR_W - 1 downto 0);
    signal cnt     : unsigned(ADDR_W downto 0);

    signal do_write : std_logic;
    signal do_read  : std_logic;

begin

    -- Guard: DEPTH must be a power of two so the circular pointer wraps cleanly
    assert is_pow2(DEPTH)
        report "sync_fifo: DEPTH must be a power of two"
        severity failure;

    do_write <= wr_en and not full;
    do_read  <= rd_en and not empty;

    full  <= '1' when cnt = DEPTH else '0';
    empty <= '1' when cnt = 0     else '0';
    count <= std_logic_vector(cnt);

    -- Single process: each signal has exactly one driver (avoids multi-driver metavalue).
    process (clk) is
    begin
        if rising_edge(clk) then
            if rst_n = '0' then
                wr_ptr  <= (others => '0');
                rd_ptr  <= (others => '0');
                cnt     <= (others => '0');
                rd_data <= (others => '0');
            else
                if do_write = '1' then
                    mem(to_integer(wr_ptr)) <= wr_data;
                    wr_ptr <= wr_ptr + 1;
                end if;
                if do_read = '1' then
                    rd_data <= mem(to_integer(rd_ptr));
                    rd_ptr  <= rd_ptr + 1;
                end if;
                case std_logic_vector'(do_write & do_read) is
                    when "10"   => cnt <= cnt + 1;
                    when "01"   => cnt <= cnt - 1;
                    when others => null;  -- "11" simultaneous r/w: count unchanged
                end case;
            end if;
        end if;
    end process;

end architecture rtl;
