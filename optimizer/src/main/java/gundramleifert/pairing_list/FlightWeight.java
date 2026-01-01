package gundramleifert.pairing_list;

public class FlightWeight {
    public static double[] flightWeight;


    private static double[] flightWeightCalcer() {
        int len = 20;
        double[] res = new double[len];
        for (int i = 0; i < res.length; i++) {
            double v = (i + 1.0) / len;
            res[i] = v * v * v;
        }
        return res;
    }

    static {
        flightWeight = flightWeightCalcer();
    }

    public static double[] getFlightWeight() {
        return flightWeight;
    }

}
