"""Finite, hardware-clocked PIO+DMA capture; requires board validation.

One state machine generates each clock and reads sample+valid before its rising
edge. Blocking autopush prevents silent sample loss; it can stretch the clock
if DMA cannot keep up. This is a bring-up capture, not an entropy certification.
"""
from array import array

def unpack_samples(words, discard=16):
    samples=bytearray()
    for index in range(16*len(words)):
        pair=(words[index//16] >> (30-2*(index%16))) & 3
        if index < discard:
            continue
        if not pair & 2:
            raise RuntimeError('Invalid sample within capture')
        samples.append(pair & 1)
    return samples

def capture(probe, count=4096, sample_hz=100000, sm_id=0):
    import machine,rp2,time
    if not hasattr(rp2,'DMA'):
        raise RuntimeError('Firmware must provide rp2.DMA')
    if count < 16 or count > 32768 or count % 16:
        raise ValueError('Sample count must be a multiple of 16 in 16..32768')
    if not 1000 <= sample_hz <= 100000 or sm_id not in range(8):
        raise ValueError('Rate 1..100 kHz; an unused state machine 0..7 is required')
    if not probe.control & 8:
        raise RuntimeError('Enable acquisition first')
    board=probe.board
    board.clock_project_stop()
    board.clk(0)
    sample_pin=board.pins.uio0.gpio_num
    if board.pins.uio1.gpio_num != sample_pin+1:
        raise RuntimeError('Sample and valid pins must be adjacent')
    clock_pin=board.pins.rp_projclk.gpio_num
    if max(clock_pin,sample_pin+1)>31:
        raise RuntimeError('This capture supports GPIO 0..31')
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW,in_shiftdir=rp2.PIO.SHIFT_LEFT,
                 autopush=True,push_thresh=32)
    def program():
        pull(block).side(0)
        mov(x,osr).side(0)
        label('sample')
        in_(pins,2).side(0)
        nop().side(1)
        jmp(x_dec,'sample').side(0)
        label('done')
        jmp('done').side(0)
    words=array('I',[0]*((count+16)//16))
    sm=rp2.StateMachine(sm_id,program,freq=sample_hz*3,
                        in_base=machine.Pin(sample_pin),sideset_base=machine.Pin(clock_pin))
    dma=rp2.DMA()
    try:
        sm.put(count+16-1)
        ctrl=dma.pack_ctrl(size=2,inc_read=False,inc_write=True,
                           treq_sel=(sm_id//4)*8+4+(sm_id%4))
        dma.config(read=sm,write=words,count=len(words),ctrl=ctrl,trigger=True)
        start=time.ticks_ms();sm.active(1)
        timeout_ms=1000+(count+16)*2000//sample_hz
        while dma.active():
            if time.ticks_diff(time.ticks_ms(),start)>timeout_ms:
                raise RuntimeError('Capture timed out')
        if dma.count or dma.unpack_ctrl(dma.ctrl)['ahb_err']:
            raise RuntimeError('Incomplete or failed DMA transfer')
        # Last autopush precedes the last rising edge. Let the finite loop finish.
        time.sleep_us(2_000_000//sample_hz+10)
        return {'samples':unpack_samples(words),'requested_sample_hz':sample_hz,
                'elapsed_ms':time.ticks_diff(time.ticks_ms(),start),
                'discarded_prefix':16,'hardware_validated':False}
    finally:
        sm.active(0);dma.active(0);dma.close()
        machine.Pin(clock_pin,machine.Pin.OUT,value=0)
