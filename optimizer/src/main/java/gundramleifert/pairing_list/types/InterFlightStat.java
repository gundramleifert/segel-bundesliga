package gundramleifert.pairing_list.types;

import java.util.ArrayList;

public class InterFlightStat {
    public ArrayList<Byte> teamsChangeBoats = new ArrayList<>();
    public ArrayList<Byte> teamsStayOnBoat = new ArrayList<>();
    public ArrayList<Byte> teamsAtWaterAtLastRace = new ArrayList<>();
    public ArrayList<Byte> teamsAtWaterAtFirstRace = new ArrayList<>();
    public int shuttleLastRace;
    public int shuttleFirstRace;
    public int shuttleBetweenFlight;
}
