using System;
using System.IO;
using System.Threading.Tasks;

internal sealed class Tape
{
    public int NDays, NEvents, MaxOffset, GatherCapacity, NTrades, Paths, TotalDays, Policies, Symbols;
    public int[] DayStart, DayEnd, Trade, Offset, EaOffset, Second, Sequence, Kind, Symbol, Cluster, Side, SwapDays, Favorable;
    public double[] Price, Stop, Slip, Remaining, SwapCash, SwapMult, Meta, Risks;
    public int[] VolumeDigits, Source;
}

internal sealed class Result
{
    public long[] I = new long[46];
    public double[] D = new double[6];
    public Result()
    {
        I[0] = 5; I[1] = 5; I[2] = 7; I[3] = 7;
        double pythonNan = BitConverter.Int64BitsToDouble(0x7ff8000000000000L);
        for (int j = 0; j < D.Length; ++j) D[j] = pythonNan;
    }
}

internal sealed class Simulator
{
    const int Slots = 16, DealDays = 4, Counters = 19;
    readonly Tape t;
    readonly int sourceBase, policy;
    readonly byte[] state = new byte[Slots];
    readonly long[] key = new long[Slots];
    readonly int[] sym = new int[Slots], cluster = new int[Slots], side = new int[Slots];
    readonly double[] intended = new double[Slots], entry = new double[Slots], stop = new double[Slots];
    readonly double[] volume = new double[Slots], current = new double[Slots], actualRisk = new double[Slots];
    readonly double[] mark = new double[Slots], fixedSlip = new double[Slots], classifierSlip = new double[Slots], swap = new double[Slots];
    readonly int[,] dealDay = new int[Slots, DealDays];
    readonly double[,] dealCash = new double[Slots, DealDays];
    readonly long[] counters = new long[Counters];
    readonly int[] gathered, gatheredOwner;
    readonly Result result = new Result();

    int phase, phaseDays, tradingDays, lastTradingDay, currentEaDay;
    int fillsToday, consecutiveLosses, freezeDay, freezeSecond, minOwnerDay;
    double balance, peakEquity, minEquity, dayStartBalance, eaDayStartBalance;
    bool dailyHalted, targetFrozen, lastFavorable;

    public Simulator(Tape tape, int path, int policyIndex)
    {
        t = tape; sourceBase = path * tape.TotalDays; policy = policyIndex;
        gathered = new int[tape.GatherCapacity];
        gatheredOwner = new int[tape.GatherCapacity];
        ResetPhase(1, 0);
    }

    void ResetPhase(int nextPhase, int nextOwnerDay)
    {
        phase = nextPhase;
        Array.Clear(state, 0, state.Length);
        for (int j = 0; j < key.Length; ++j) key[j] = -1;
        balance = 100000.0; peakEquity = 100000.0; minEquity = 100000.0;
        phaseDays = 0; tradingDays = 0; lastTradingDay = -1;
        currentEaDay = Int32.MinValue; dayStartBalance = 100000.0; eaDayStartBalance = 100000.0;
        fillsToday = 0; consecutiveLosses = 0; dailyHalted = false;
        targetFrozen = false; freezeDay = -1; freezeSecond = -1; lastFavorable = false;
        Array.Clear(counters, 0, counters.Length);
        for (int s = 0; s < Slots; ++s)
            for (int d = 0; d < DealDays; ++d) { dealDay[s, d] = Int32.MinValue; dealCash[s, d] = 0.0; }
        minOwnerDay = nextOwnerDay;
    }

    double Meta(int symbol, int field) { return t.Meta[symbol * 6 + field]; }
    double Risk(int symbol) { return t.Risks[(policy * 2 + (phase - 1)) * t.Symbols + symbol]; }

    double Cash(double entryPrice, double eventPrice, int eventSide, double lots, int symbol)
    {
        double move = (eventPrice - entryPrice) * eventSide;
        if (Math.Abs(move) <= 1e-9 || lots <= 0.0) return 0.0;
        double tickValue = move > 0.0 ? Meta(symbol, 2) : Meta(symbol, 1);
        double value = Math.Abs(move) / Meta(symbol, 0) * tickValue * lots;
        return move > 0.0 ? value : -value;
    }

    int Find(long wanted)
    {
        for (int s = 0; s < Slots; ++s) if (state[s] != 0 && key[s] == wanted) return s;
        return -1;
    }

    int NewSlot()
    {
        for (int s = 0; s < Slots; ++s) if (state[s] == 0) return s;
        throw new InvalidDataException("runtime slot overflow");
    }

    int ActiveCount()
    {
        int n = 0;
        for (int s = 0; s < Slots; ++s) if (state[s] == 1 || state[s] == 2) ++n;
        return n;
    }

    bool HasActive() { return ActiveCount() != 0; }

    void CancelPending(int counterIndex)
    {
        for (int s = 0; s < Slots; ++s)
            if (state[s] == 1) { state[s] = 3; counters[counterIndex]++; }
    }

    void Equities(out double marked, out double tested)
    {
        double markedPositions = 0.0, conservativePositions = 0.0;
        for (int s = 0; s < Slots; ++s)
        {
            if (state[s] != 2) continue;
            double priceCash = Cash(entry[s], mark[s], side[s], current[s], sym[s]);
            markedPositions += priceCash + swap[s];
            double envelope = -(stop[s] / Meta(sym[s], 0) * Meta(sym[s], 1) * current[s]);
            conservativePositions += Math.Min(priceCash, envelope) + swap[s];
        }
        marked = balance + markedPositions;
        double conservative = balance + conservativePositions;
        tested = lastFavorable ? marked : conservative;
    }

    bool CheckRails(out int status, out int reason)
    {
        double marked, tested; Equities(out marked, out tested);
        peakEquity = Math.Max(peakEquity, marked); minEquity = Math.Min(minEquity, tested);
        status = 0; reason = 0;
        if (tested <= dayStartBalance - 5000.0 + 1e-9) { status = 2; reason = 2; }
        else if (tested <= 90000.0 + 1e-9) { status = 2; reason = 3; }
        else if (tested <= peakEquity * 0.92 + 1e-9) { status = 3; reason = 4; }
        else if (tested <= 91000.0 + 1e-9) { status = 3; reason = 5; }
        else if (!dailyHalted && tested <= eaDayStartBalance * 0.96 + 1e-9)
        {
            dailyHalted = true; counters[15]++; CancelPending(3);
        }
        return status != 0;
    }

    void Capture(int status, int reason)
    {
        int p = phase - 1;
        result.I[p] = status; result.I[2 + p] = reason;
        result.I[4 + p] = phaseDays; result.I[6 + p] = tradingDays;
        result.D[p] = balance; result.D[2 + p] = minEquity; result.D[4 + p] = peakEquity;
        for (int c = 0; c < Counters; ++c) result.I[8 + p * Counters + c] = counters[c];
    }

    bool CanPass(double target) { return !HasActive() && balance + 1e-9 >= target && tradingDays >= 4; }

    void RefreshFreeze(int replayDay, int second, double target)
    {
        if (!targetFrozen && balance + 1e-9 >= target && tradingDays >= 4)
        { targetFrozen = true; freezeDay = replayDay; freezeSecond = second; }
    }

    void AdvanceTime(int replayDay, int second)
    {
        if (targetFrozen && (replayDay > freezeDay || (replayDay == freezeDay && second > freezeSecond)))
            CancelPending(2);
    }

    double RecordDeal(int slot, int eaDay, double cash)
    {
        for (int d = 0; d < DealDays; ++d)
            if (dealDay[slot, d] == eaDay) { dealCash[slot, d] += cash; return dealCash[slot, d]; }
        for (int d = 0; d < DealDays; ++d)
            if (dealDay[slot, d] == Int32.MinValue)
            { dealDay[slot, d] = eaDay; dealCash[slot, d] = cash; return cash; }
        throw new InvalidDataException("deal day capacity exceeded");
    }

    int Gather(int replayDay)
    {
        int count = 0; int ownerFirst = Math.Max(minOwnerDay, replayDay - t.MaxOffset);
        for (int owner = ownerFirst; owner <= replayDay; ++owner)
        {
            int source = t.Source[sourceBase + owner]; int wanted = replayDay - owner;
            for (int e = t.DayStart[source]; e < t.DayEnd[source]; ++e)
            {
                if (t.Offset[e] != wanted) continue;
                if (count >= gathered.Length) throw new InvalidDataException("gather capacity exceeded");
                int pos = count;
                while (pos > 0)
                {
                    int prior = gathered[pos - 1];
                    if (t.Second[prior] < t.Second[e] ||
                        (t.Second[prior] == t.Second[e] && t.Sequence[prior] < t.Sequence[e])) break;
                    gathered[pos] = gathered[pos - 1]; gatheredOwner[pos] = gatheredOwner[pos - 1]; --pos;
                }
                gathered[pos] = e; gatheredOwner[pos] = owner; ++count;
            }
        }
        return count;
    }

    void ProcessEvent(int e, int owner, int replayDay, int eaDay)
    {
        int kind = t.Kind[e]; long tradeKey = (long)owner * t.NTrades + t.Trade[e];
        int existing = Find(tradeKey);
        lastFavorable = (kind == 3 || kind == 5) && t.Favorable[e] != 0;
        if (kind == 0)
        {
            int slot = NewSlot(); key[slot] = tradeKey;
            if (targetFrozen) { counters[10]++; state[slot] = 3; return; }
            if (dailyHalted) { counters[11]++; state[slot] = 3; return; }
            if (fillsToday >= 8) { counters[12]++; state[slot] = 3; return; }
            if (consecutiveLosses >= 4) { counters[13]++; state[slot] = 3; return; }
            int eventSymbol = t.Symbol[e], active = ActiveCount(), clusterCount = 0; bool okay = active < 2;
            for (int q = 0; q < Slots; ++q) if (state[q] == 1 || state[q] == 2)
            {
                if (sym[q] == eventSymbol) okay = false;
                if (cluster[q] == t.Cluster[e]) clusterCount++;
            }
            if (clusterCount >= 1) okay = false;
            if (!okay) throw new InvalidDataException("account capacity overlap");
            double requested = balance * Risk(eventSymbol);
            double lossPerLot = t.Stop[e] / Meta(eventSymbol, 0) * Meta(eventSymbol, 1);
            double raw = requested / lossPerLot;
            double sized = Math.Floor(raw / Meta(eventSymbol, 4)) * Meta(eventSymbol, 4);
            bool substituted = false, rejected = false;
            if (sized + 1e-12 < Meta(eventSymbol, 3))
            {
                double minRisk = lossPerLot * Meta(eventSymbol, 3);
                if (minRisk > requested * 1.5 + 1e-9) rejected = true;
                else { sized = Meta(eventSymbol, 3); substituted = true; }
            }
            if (sized > Meta(eventSymbol, 5)) sized = Meta(eventSymbol, 5);
            if (sized + 1e-12 < Meta(eventSymbol, 3)) rejected = true;
            if (rejected) { counters[8]++; state[slot] = 3; return; }
            if (substituted) counters[9]++;
            state[slot] = 1; sym[slot] = eventSymbol; cluster[slot] = t.Cluster[e]; side[slot] = t.Side[e];
            intended[slot] = t.Price[e]; stop[slot] = t.Stop[e]; volume[slot] = sized;
            actualRisk[slot] = lossPerLot * sized; counters[0]++;
            counters[18] = Math.Max(counters[18], ActiveCount()); return;
        }
        if (kind == 1)
        {
            if (existing >= 0 && state[existing] == 1)
            { state[existing] = 0; key[existing] = -1; counters[1]++; }
            else if (existing >= 0 && state[existing] == 3)
            { state[existing] = 0; key[existing] = -1; }
            else counters[14]++;
            return;
        }
        if (existing >= 0 && state[existing] == 3)
        {
            counters[14]++;
            if (kind == 6) { state[existing] = 0; key[existing] = -1; }
            return;
        }
        if (kind == 2)
        {
            if (existing < 0 || state[existing] != 1) { counters[14]++; return; }
            int slot = existing;
            if (Math.Abs(t.Price[e] - intended[slot]) > 1e-9) throw new InvalidDataException("entry price changed");
            double slipCash = t.Slip[e] * actualRisk[slot]; balance -= slipCash;
            state[slot] = 2; entry[slot] = t.Price[e]; current[slot] = volume[slot]; mark[slot] = t.Price[e];
            fixedSlip[slot] = slipCash; classifierSlip[slot] = 0.0; swap[slot] = 0.0;
            for (int d = 0; d < DealDays; ++d) { dealDay[slot, d] = Int32.MinValue; dealCash[slot, d] = 0.0; }
            fillsToday++;
            if (lastTradingDay != replayDay) { tradingDays++; lastTradingDay = replayDay; }
            counters[4]++; counters[18] = Math.Max(counters[18], ActiveCount()); return;
        }
        if (existing < 0 || state[existing] != 2) { counters[14]++; return; }
        if (kind == 3) { mark[existing] = t.Price[e]; return; }
        if (kind == 4)
        {
            if (t.SwapCash[e] > 0.0) counters[17]++;
            else swap[existing] += t.SwapCash[e] * t.SwapDays[e] * t.SwapMult[e] * current[existing];
            counters[16]++; return;
        }
        if (kind == 5)
        {
            int slot = existing, eventSymbol = sym[slot]; double requestedClose = 1.0 - t.Remaining[e];
            double rawClose = volume[slot] * requestedClose, closeVolume = 0.0;
            if (rawClose + 1e-12 >= Meta(eventSymbol, 3))
            {
                double units = Math.Floor((rawClose + 1e-12) / Meta(eventSymbol, 4));
                double candidate = Math.Round(units * Meta(eventSymbol, 4), t.VolumeDigits[eventSymbol], MidpointRounding.ToEven);
                if (candidate + 1e-12 >= Meta(eventSymbol, 3) &&
                    volume[slot] - candidate + 1e-12 >= Meta(eventSymbol, 3)) closeVolume = candidate;
            }
            if (closeVolume <= 0.0) counters[7]++;
            else
            {
                double cash = Cash(entry[slot], t.Price[e], side[slot], closeVolume, eventSymbol);
                double slipPiece = -fixedSlip[slot] * (closeVolume / volume[slot]);
                classifierSlip[slot] += slipPiece; RecordDeal(slot, eaDay, cash + slipPiece);
                balance += cash; current[slot] -= closeVolume; counters[6]++;
            }
            mark[slot] = t.Price[e]; return;
        }
        if (kind == 6)
        {
            int slot = existing, eventSymbol = sym[slot];
            double priceCash = Cash(entry[slot], t.Price[e], side[slot], current[slot], eventSymbol);
            double finalSlip = -fixedSlip[slot] - classifierSlip[slot];
            double finalDeal = priceCash + finalSlip + swap[slot];
            double classifierCash = RecordDeal(slot, eaDay, finalDeal);
            balance += priceCash + swap[slot];
            if (classifierCash < -1e-9) consecutiveLosses++;
            else if (classifierCash > 1e-9) consecutiveLosses = 0;
            state[slot] = 0; key[slot] = -1; counters[5]++; return;
        }
        throw new InvalidDataException("unsupported event kind");
    }

    public Result Run()
    {
        for (int replayDay = 0; replayDay < t.TotalDays; ++replayDay)
        {
            phaseDays++; dayStartBalance = balance; lastFavorable = false;
            AdvanceTime(replayDay, -1);
            int status, reason;
            if (CheckRails(out status, out reason)) { Capture(status, reason); return result; }
            double target = phase == 1 ? 110000.0 : 105000.0;
            RefreshFreeze(replayDay, -1, target);
            if (CanPass(target))
            {
                Capture(1, 1); if (phase == 2) return result;
                ResetPhase(2, replayDay + 1); continue;
            }
            int count = Gather(replayDay); bool transitioned = false;
            for (int pos = 0; pos < count; ++pos)
            {
                int e = gathered[pos], owner = gatheredOwner[pos], eaDay = owner + t.EaOffset[e];
                if (currentEaDay != eaDay)
                {
                    currentEaDay = eaDay; eaDayStartBalance = balance; fillsToday = 0;
                    consecutiveLosses = 0; dailyHalted = false;
                }
                int second = t.Second[e]; AdvanceTime(replayDay, second);
                if (CheckRails(out status, out reason)) { Capture(status, reason); return result; }
                RefreshFreeze(replayDay, second, target);
                if (CanPass(target)) { Capture(1, 1); transitioned = true; break; }
                ProcessEvent(e, owner, replayDay, eaDay);
                if (CheckRails(out status, out reason)) { Capture(status, reason); return result; }
                RefreshFreeze(replayDay, second, target);
                if (CanPass(target)) { Capture(1, 1); transitioned = true; break; }
            }
            if (transitioned)
            {
                if (phase == 2) return result;
                ResetPhase(2, replayDay + 1); continue;
            }
            if (phaseDays >= 3650) { Capture(4, 6); return result; }
        }
        throw new InvalidDataException("source stream exhausted");
    }
}

internal static class Program
{
    static int[] ReadInts(BinaryReader br, int n)
    { int[] x = new int[n]; for (int i = 0; i < n; ++i) x[i] = br.ReadInt32(); return x; }
    static double[] ReadDoubles(BinaryReader br, int n)
    { double[] x = new double[n]; for (int i = 0; i < n; ++i) x[i] = br.ReadDouble(); return x; }

    static Tape ReadTape(string path)
    {
        using (BinaryReader br = new BinaryReader(File.OpenRead(path)))
        {
            if (br.ReadInt32() != 0x56313330) throw new InvalidDataException("bad input magic");
            Tape t = new Tape();
            t.NDays = br.ReadInt32(); t.NEvents = br.ReadInt32(); t.MaxOffset = br.ReadInt32();
            t.GatherCapacity = br.ReadInt32(); t.NTrades = br.ReadInt32(); t.Paths = br.ReadInt32();
            t.TotalDays = br.ReadInt32(); t.Policies = br.ReadInt32(); t.Symbols = br.ReadInt32();
            t.DayStart = ReadInts(br, t.NDays); t.DayEnd = ReadInts(br, t.NDays);
            t.Trade = ReadInts(br, t.NEvents); t.Offset = ReadInts(br, t.NEvents);
            t.EaOffset = ReadInts(br, t.NEvents); t.Second = ReadInts(br, t.NEvents);
            t.Sequence = ReadInts(br, t.NEvents); t.Kind = ReadInts(br, t.NEvents);
            t.Symbol = ReadInts(br, t.NEvents); t.Cluster = ReadInts(br, t.NEvents);
            t.Side = ReadInts(br, t.NEvents); t.SwapDays = ReadInts(br, t.NEvents);
            t.Favorable = ReadInts(br, t.NEvents);
            t.Price = ReadDoubles(br, t.NEvents); t.Stop = ReadDoubles(br, t.NEvents);
            t.Slip = ReadDoubles(br, t.NEvents); t.Remaining = ReadDoubles(br, t.NEvents);
            t.SwapCash = ReadDoubles(br, t.NEvents); t.SwapMult = ReadDoubles(br, t.NEvents);
            t.Meta = ReadDoubles(br, t.Symbols * 6); t.VolumeDigits = ReadInts(br, t.Symbols);
            t.Risks = ReadDoubles(br, t.Policies * 2 * t.Symbols);
            t.Source = ReadInts(br, t.Paths * t.TotalDays);
            if (br.BaseStream.Position != br.BaseStream.Length) throw new InvalidDataException("trailing input bytes");
            return t;
        }
    }

    static int Main(string[] args)
    {
        try
        {
            if (args.Length != 2) throw new ArgumentException("usage: kernel input.bin output.bin");
            Tape t = ReadTape(args[0]);
            Result[,] results = new Result[t.Paths, t.Policies];
            Parallel.For(0, t.Paths, delegate(int path)
            {
                for (int policy = 0; policy < t.Policies; ++policy)
                    results[path, policy] = new Simulator(t, path, policy).Run();
            });
            using (BinaryWriter bw = new BinaryWriter(File.Create(args[1])))
            {
                for (int path = 0; path < t.Paths; ++path)
                    for (int policy = 0; policy < t.Policies; ++policy)
                    {
                        Result r = results[path, policy];
                        for (int j = 0; j < r.I.Length; ++j) bw.Write(r.I[j]);
                        for (int j = 0; j < r.D.Length; ++j) bw.Write(r.D[j]);
                    }
            }
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.ToString()); return 1;
        }
    }
}
