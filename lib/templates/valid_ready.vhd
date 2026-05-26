-- valid_ready.vhd — One-way handshake (valid/ready) pipeline register
--
-- Implements a single-stage pipeline register with valid/ready flow control.
-- A transaction occurs when both valid_i and ready_o are high on the same
-- rising clock edge.  The stage holds data until the downstream consumer
-- is ready to accept it.
--
-- This is the fundamental building block of AXI-style data pipelines.
--
-- Generics:
--   DATA_W : width of the data bus (default 8 bits)
--
-- Ports:
--   clk     : system clock
--   rst_n   : synchronous reset, active low
--   valid_i : upstream data valid
--   data_i  : upstream data
--   ready_o : upstream ready (backpressure)
--   valid_o : downstream data valid
--   data_o  : downstream data
--   ready_i : downstream ready
--
-- Waveform (DATA_W=8, single transfer):
--
--   clk     : __|‾|_|‾|_|‾|_|‾|_
--   valid_i : _____|‾‾‾‾‾‾‾|____
--   data_i  : -----< 0xAB >-----
--   ready_o : ‾‾‾‾‾‾‾‾‾|___|‾‾‾  (de-asserts when stage is full)
--   valid_o : _________|‾‾‾|____
--   data_o  : ---------< 0xAB >-
--   ready_i : ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

library ieee;
use ieee.std_logic_1164.all;

entity valid_ready is
    generic (
        DATA_W : positive := 8
    );
    port (
        clk     : in  std_logic;
        rst_n   : in  std_logic;

        -- Upstream (producer)
        valid_i : in  std_logic;
        data_i  : in  std_logic_vector(DATA_W - 1 downto 0);
        ready_o : out std_logic;

        -- Downstream (consumer)
        valid_o : out std_logic;
        data_o  : out std_logic_vector(DATA_W - 1 downto 0);
        ready_i : in  std_logic
    );
end entity valid_ready;

architecture rtl of valid_ready is

    signal full : std_logic;
    signal buf  : std_logic_vector(DATA_W - 1 downto 0);

begin

    ready_o <= not full;
    valid_o <= full;
    data_o  <= buf;

    process (clk) is
    begin
        if rising_edge(clk) then
            if rst_n = '0' then
                full <= '0';
                buf  <= (others => '0');
            else
                if full = '0' then
                    -- Stage is empty: accept upstream data if presented
                    if valid_i = '1' then
                        buf  <= data_i;
                        full <= '1';
                    end if;
                else
                    -- Stage is full: release to downstream when it is ready
                    if ready_i = '1' then
                        if valid_i = '1' then
                            -- Back-to-back: consume and reload in one cycle
                            buf  <= data_i;
                        else
                            full <= '0';
                        end if;
                    end if;
                end if;
            end if;
        end if;
    end process;

end architecture rtl;
