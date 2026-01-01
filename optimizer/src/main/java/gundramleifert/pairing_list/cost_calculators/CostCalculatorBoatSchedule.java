package gundramleifert.pairing_list.cost_calculators;

import gundramleifert.pairing_list.configs.OptBoatConfig;
import gundramleifert.pairing_list.types.*;
import gundramleifert.pairing_list.configs.ScheduleConfig;

import java.util.ArrayList;

import static gundramleifert.pairing_list.FlightWeight.getFlightWeight;

public class CostCalculatorBoatSchedule implements ICostCalculator {

    private ScheduleConfig properties;
    private OptBoatConfig optBoatUsage;

    public CostCalculatorBoatSchedule(ScheduleConfig properties, OptBoatConfig optBoatUsage) {
        this.properties = properties;
        this.optBoatUsage = optBoatUsage;
    }

    private static int addteamsOnWaterAndReturnTeamsToTransfer(ArrayList<Byte> teamsAtWater, Race race1, Race race2) {
        int teamsToTranfer = Math.max(race1.teams.length, race2.teams.length);
        for (int i = 0; i < race1.teams.length; i++) {
            byte team1 = race1.teams[i];
            for (int j = 0; j < race2.teams.length; j++) {
                byte team2 = race2.teams[j];
                if (team1 == team2) {
                    teamsAtWater.add(team1);
                    teamsToTranfer--;
                    break;
                }
            }
        }
        return teamsToTranfer;
    }

    public static int[]  getInterFlightStat(Schedule schedule, int numTeams) {
        int shuttleAtHabour = 0;
        int shuttleAtSea = 0;
        int shuttlesEachRace = shuttlesPerTeams(schedule.get(0).races[0].teams.length);
        int boatChanges = 0;
        for (int i = 1; i < schedule.size(); i++) {
            InterFlightStat interFlightStat = getInterFlightStat(schedule.get(i - 1), schedule.get(i),numTeams);
            shuttleAtHabour += (shuttlesEachRace - shuttlesPerTeams(interFlightStat.shuttleBetweenFlight));
            shuttleAtSea += (shuttlesEachRace - shuttlesPerTeams(interFlightStat.shuttleFirstRace));
            shuttleAtSea += (shuttlesEachRace - shuttlesPerTeams(interFlightStat.shuttleLastRace));
            boatChanges += interFlightStat.teamsChangeBoats.size();
        }
        return new int[]{shuttleAtHabour, shuttleAtSea, boatChanges};
    }

    public static InterFlightStat getInterFlightStat(Flight before, Flight after,int numTeams) {
        InterFlightStat res = new InterFlightStat();
        Race race1 = before.races[before.races.length - 1];
        Race race2 = after.races[0];
        int teamsToTranfer = Math.max(race1.numParticipants(numTeams),
                race2.numParticipants(numTeams));
        for (int i = 0; i < race1.teams.length; i++) {
            byte team1 = race1.teams[i];
            for (int j = 0; j < race2.teams.length; j++) {
                byte team2 = race2.teams[j];
                if (team1 == team2) {
                    if (i == j) {
                        res.teamsStayOnBoat.add(team1);
                        teamsToTranfer--;
                    } else {
                        res.teamsChangeBoats.add(team1);
                    }
                }
            }
        }
        res.shuttleBetweenFlight = teamsToTranfer;
        if (before.races.length > 1) {
            res.shuttleLastRace = addteamsOnWaterAndReturnTeamsToTransfer(
                    res.teamsAtWaterAtLastRace,
                    before.races[before.races.length - 2],
                    after.races[0]);
            res.shuttleFirstRace = addteamsOnWaterAndReturnTeamsToTransfer(
                    res.teamsAtWaterAtFirstRace,
                    before.races[before.races.length - 1],
                    after.races[1]);
        }
        return res;
        //TODO: max? then shuttle always on water, min? 1 boat can sail to habour

        // neededShuttles += (Math.max(race1.teams.length, race2.teams.length) + 1 - stayOnBoats) / 2;
        //changesBetweenBoats += changesBetweenBoatsActual;

    }

    public static int shuttlesPerTeams(int teams) {
        return (teams + 1) / 2;
    }

    public double score(Schedule schedule) {
        double res = 0;
        BoatMatrix matchMatrix = new BoatMatrix(properties);
        double resPart = 0;
        for (int flightIdx = 0; flightIdx < schedule.size(); flightIdx++) {
            Flight flight = schedule.get(flightIdx);
            matchMatrix.add(flight);
            double avg = matchMatrix.average();
            for (byte[] vec : matchMatrix.mat) {
                for (byte v : vec) {
                    resPart += (int) Math.abs(v - avg);
                    //resPart +=(v - avg)*(v - avg);
                }
            }
            if (flightIdx > 0) {
                InterFlightStat interFlightStat = getInterFlightStat(
                        schedule.get(flightIdx - 1),
                        schedule.get(flightIdx),properties.numTeams);
                resPart += interFlightStat.teamsChangeBoats.size() * optBoatUsage.weightChangeBetweenBoats;
                resPart += (shuttlesPerTeams(interFlightStat.shuttleFirstRace) + 0.01 * interFlightStat.shuttleFirstRace) * optBoatUsage.weightStayOnShuttle;
                resPart += (shuttlesPerTeams(interFlightStat.shuttleLastRace) + 0.01 * interFlightStat.shuttleFirstRace) * optBoatUsage.weightStayOnShuttle;
                resPart += (shuttlesPerTeams(interFlightStat.shuttleBetweenFlight) + 0.01 * interFlightStat.shuttleBetweenFlight) * optBoatUsage.weightStayOnBoat;
            }

            res += resPart;
        }
        return res;
    }
}


